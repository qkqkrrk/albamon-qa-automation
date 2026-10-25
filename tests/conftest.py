import logging
import os
from datetime import datetime
from typing import Generator

import pytest
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.remote.webdriver import WebDriver
from webdriver_manager.chrome import ChromeDriverManager

logger = logging.getLogger(__name__)


def _build_chrome_options() -> Options:
    """테스트 안정성 및 봇 탐지(User-Agent 등) 우회를 위한 Chrome 옵션을 구성합니다."""
    options = Options()

    # 환경변수 HEADLESS 설정 확인 (기본값: 로컬은 false, 원격/CI 환경은 docker-compose에서 true로 주입)
    headless_env = os.getenv("HEADLESS", "false").lower()
    if headless_env in ("true", "1", "yes"):
        options.add_argument("--headless=new")

    # Docker 컨테이너 및 리눅스 환경 안정성 확보를 위한 필수 옵션
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1920,1080")
    options.add_argument("--lang=ko-KR")

    # 자동화 브라우저 감지 완화 설정 (실제 상용 웹사이트 테스트 시 차단 방지)
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_argument(
        "user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36"
    )
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option("useAutomationExtension", False)

    return options


@pytest.fixture(scope="function")
def driver() -> Generator[WebDriver, None, None]:
    """환경변수(RUN_ENV)에 따라 Local WebDriver 또는 Remote WebDriver(Selenium Grid)를
    생성하고 테스트 종료 후 안전하게 리소스를 해제하는 Pytest Fixture.

    환경변수 가이드:
    - RUN_ENV=local (기본값): 로컬 PC의 Chrome 브라우저(또는 Selenium Manager)로 실행
    - RUN_ENV=remote: SELENIUM_REMOTE_URL에 지정된 Docker Standalone Chrome 컨테이너로 실행
    """
    run_env = os.getenv("RUN_ENV", "local").lower()
    remote_url = os.getenv("SELENIUM_REMOTE_URL", "http://localhost:4444/wd/hub")
    options = _build_chrome_options()

    web_driver: WebDriver | None = None

    try:
        if run_env == "remote":
            logger.info(f"[Remote WebDriver] 연결 시작 -> {remote_url}")
            web_driver = webdriver.Remote(
                command_executor=remote_url,
                options=options,
            )
        else:
            logger.info("[Local WebDriver] 로컬 Chrome 브라우저 초기화 시작")
            try:
                # Selenium 4.6+ 내장 Selenium Manager를 우선 활용
                web_driver = webdriver.Chrome(options=options)
            except Exception:
                # 필요 시 webdriver-manager로 폴백
                service = Service(ChromeDriverManager().install())
                web_driver = webdriver.Chrome(service=service, options=options)

        # navigator.webdriver 플래그 제거 (봇 차단 방지 보조)
        try:
            web_driver.execute_cdp_cmd(
                "Page.addScriptToEvaluateOnNewDocument",
                {
                    "source": "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
                },
            )
        except Exception:
            # Remote WebDriver 등 CDP 미지원 환경에서는 안전하게 패스
            pass

        yield web_driver

    finally:
        if web_driver is not None:
            logger.info("WebDriver 세션 종료")
            web_driver.quit()


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item: pytest.Item, call: pytest.CallInfo):
    """테스트 실패 시 자동으로 브라우저 스크린샷을 캡처하여
    reports/screenshots/ 디렉토리에 저장하고 pytest-html 리포트에 첨부하는 Hook.
    """
    outcome = yield
    report = outcome.get_result()

    # 실제 테스트 함수 실행 단계('call') 또는 셋업 단계('setup')에서 실패한 경우에만 캡처 수행
    if report.when in ("call", "setup") and report.failed:
        driver_instance: WebDriver | None = item.funcargs.get("driver")
        if driver_instance is None:
            return

        screenshot_dir = os.path.join(os.getcwd(), "reports", "screenshots")
        os.makedirs(screenshot_dir, exist_ok=True)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        test_name = item.name
        safe_test_name = "".join(
            c if c.isalnum() or c in ("_", "-") else "_" for c in test_name
        )
        file_name = f"FAIL_{safe_test_name}_{timestamp}.png"
        file_path = os.path.join(screenshot_dir, file_name)

        try:
            driver_instance.save_screenshot(file_path)
            logger.error(f"[테스트 실패] 자동 스크린샷 캡처 완료: {file_path}")

            # pytest-html 플러그인이 활성화된 경우 HTML 리포트에 스크린샷 이미지 임베딩
            pytest_html = item.config.pluginmanager.getplugin("html")
            if pytest_html is not None:
                extra = getattr(report, "extra", [])
                # reports/report.html 기준 상대 경로로 연결
                relative_path = os.path.join("screenshots", file_name)
                extra.append(pytest_html.extras.image(relative_path))
                extra.append(
                    pytest_html.extras.url(
                        driver_instance.current_url, name="실패 시점 URL"
                    )
                )
                report.extra = extra
        except Exception as e:
            logger.error(f"실패 스크린샷 저장 중 오류 발생: {e}")
