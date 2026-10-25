import logging
import os
from datetime import datetime
from typing import List, Tuple

from selenium.common.exceptions import TimeoutException, WebDriverException
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.remote.webdriver import WebDriver
from selenium.webdriver.remote.webelement import WebElement
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

logger = logging.getLogger(__name__)

Locator = Tuple[str, str]


class BasePage:
    """모든 Page Object 클래스의 최상위 부모 클래스.

    time.sleep() 하드코딩을 배제하고 Selenium의 Explicit Wait(WebDriverWait)를
    캡슐화하여 안정적인 UI 요소 탐색 및 인터랙션 메서드를 제공합니다.
    """

    DEFAULT_TIMEOUT = 15

    def __init__(self, driver: WebDriver, timeout: int = DEFAULT_TIMEOUT) -> None:
        self.driver = driver
        self.timeout = timeout
        self.wait = WebDriverWait(self.driver, self.timeout)

    def open_url(self, url: str) -> None:
        """지정된 URL로 이동하고 문서 로드가 완료될 때까지 대기합니다."""
        logger.info(f"페이지 이동: {url}")
        self.driver.get(url)
        self.wait_for_page_load()

    def wait_for_page_load(self, timeout: int = DEFAULT_TIMEOUT) -> None:
        """브라우저의 document.readyState가 'complete'가 될 때까지 명시적으로 대기합니다."""
        WebDriverWait(self.driver, timeout).until(
            lambda d: d.execute_script("return document.readyState") == "complete",
            message="페이지 로딩(document.readyState == complete) 대기 시간 초과",
        )

    def find_element(self, locator: Locator, timeout: int | None = None) -> WebElement:
        """요소가 DOM에 나타나고 화면에 노출(visibility)될 때까지 대기한 후 반환합니다."""
        wait_time = timeout or self.timeout
        try:
            return WebDriverWait(self.driver, wait_time).until(
                EC.visibility_of_element_located(locator)
            )
        except TimeoutException as e:
            logger.error(f"요소 탐색 실패 (Visibility Timeout): {locator}")
            raise TimeoutException(f"요소를 찾을 수 없습니다: {locator}") from e

    def find_present_element(self, locator: Locator, timeout: int | None = None) -> WebElement:
        """요소가 DOM에 존재(presence)할 때까지 대기한 후 반환합니다."""
        wait_time = timeout or self.timeout
        try:
            return WebDriverWait(self.driver, wait_time).until(
                EC.presence_of_element_located(locator)
            )
        except TimeoutException as e:
            logger.error(f"요소 탐색 실패 (Presence Timeout): {locator}")
            raise TimeoutException(f"DOM에서 요소를 찾을 수 없습니다: {locator}") from e

    def find_elements(self, locator: Locator, timeout: int | None = None) -> List[WebElement]:
        """조건에 일치하는 요소들이 최소 1개 이상 DOM에 존재할 때까지 대기 후 리스트로 반환합니다."""
        wait_time = timeout or self.timeout
        try:
            WebDriverWait(self.driver, wait_time).until(
                EC.presence_of_element_located(locator)
            )
            return self.driver.find_elements(*locator)
        except TimeoutException:
            logger.warning(f"일치하는 요소 리스트가 없습니다: {locator}")
            return []

    def click(self, locator: Locator, timeout: int | None = None) -> None:
        """요소가 클릭 가능(element_to_be_clickable)해질 때까지 대기한 후 클릭합니다.
        일반 클릭이 가로채기(Intercepted) 등으로 실패할 경우 JavaScript 클릭으로 폴백(Fallback)합니다.
        """
        wait_time = timeout or self.timeout
        try:
            element = WebDriverWait(self.driver, wait_time).until(
                EC.element_to_be_clickable(locator)
            )
            logger.info(f"요소 클릭 시도: {locator}")
            element.click()
        except WebDriverException as e:
            logger.warning(f" 기본 클릭 실패 ({e.__class__.__name__}), JS 클릭으로 재시도: {locator}")
            element = self.find_present_element(locator, timeout=wait_time)
            self.driver.execute_script("arguments[0].click();", element)

    def input_text(
        self,
        locator: Locator,
        text: str,
        clear_first: bool = True,
        press_enter: bool = False,
    ) -> None:
        """입력 필드가 노출될 때까지 대기한 후 텍스트를 입력합니다."""
        element = self.find_element(locator)
        if clear_first:
            element.clear()
        logger.info(f"텍스트 입력: '{text}' -> {locator}")
        element.send_keys(text)
        if press_enter:
            logger.info("Enter 키 입력 실행")
            element.send_keys(Keys.ENTER)

    def wait_for_url_contains(self, url_fragment: str, timeout: int | None = None) -> bool:
        """현재 URL에 특정 문자열이 포함될 때까지 대기합니다."""
        wait_time = timeout or self.timeout
        return WebDriverWait(self.driver, wait_time).until(
            EC.url_contains(url_fragment),
            message=f"URL에 '{url_fragment}'가 포함되지 않았습니다. 현재 URL: {self.driver.current_url}",
        )

    def switch_to_latest_window(self) -> None:
        """새 탭이나 새 창이 열렸을 경우 가장 최근에 열린 창으로 포커스를 전환합니다."""
        handles = self.driver.window_handles
        if len(handles) > 1:
            logger.info(f"새 창/탭 감지됨 (총 {len(handles)}개). 최신 탭으로 전환합니다.")
            self.driver.switch_to.window(handles[-1])
            self.wait_for_page_load()

    def get_title(self) -> str:
        """현재 페이지의 브라우저 타이틀을 반환합니다."""
        return self.driver.title

    def get_current_url(self) -> str:
        """현재 페이지의 URL을 반환합니다."""
        return self.driver.current_url

    def save_screenshot(self, name_prefix: str = "screenshot") -> str:
        """reports/screenshots/ 경로에 타임스탬프가 포함된 스크린샷을 저장하고 파일 경로를 반환합니다."""
        screenshot_dir = os.path.join(os.getcwd(), "reports", "screenshots")
        os.makedirs(screenshot_dir, exist_ok=True)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        safe_prefix = "".join(c if c.isalnum() or c in ("_", "-") else "_" for c in name_prefix)
        file_name = f"{safe_prefix}_{timestamp}.png"
        file_path = os.path.join(screenshot_dir, file_name)

        self.driver.save_screenshot(file_path)
        logger.info(f"스크린샷 저장 완료: {file_path}")
        return file_path
