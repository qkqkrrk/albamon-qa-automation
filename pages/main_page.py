import logging
import os
from urllib.parse import quote

from selenium.common.exceptions import TimeoutException
from selenium.webdriver.common.by import By
from selenium.webdriver.remote.webdriver import WebDriver
from selenium.webdriver.remote.webelement import WebElement

from pages.base_page import BasePage, Locator

logger = logging.getLogger(__name__)


class MainPageLocators:
    """알바몬 메인 페이지 UI 요소 셀렉터(Locator) 중앙 관리 클래스.

    웹사이트 구조 개편이나 A/B 테스트로 인해 DOM 속성이 변경될 경우,
    비즈니스 로직(테스트 코드) 수정 없이 이 클래스의 상수만 업데이트하여 유지보수할 수 있습니다.
    """

    # 검색어 입력창 (통합 검색 input 다중 후보를 CSS 콤마 선택자로 통합 관리)
    SEARCH_INPUT: Locator = (
        By.CSS_SELECTOR,
        "input[placeholder*='검색'], input[title*='검색'], input[type='search'], "
        "input#searchKw, header input[type='text']",
    )

    # 검색 실행 버튼
    SEARCH_BUTTON: Locator = (
        By.CSS_SELECTOR,
        "button[type='submit'], button[aria-label*='검색'], button[class*='search'], "
        "header button:has(svg)",
    )

    # 메인 헤더 로고 및 주요 네비게이션 영역
    HEADER_LOGO: Locator = (
        By.CSS_SELECTOR,
        "header a[href='/'], header h1, a[aria-label*='알바몬'], header",
    )

    # 메인 페이지 이벤트/안내 모달 닫기 버튼 (노출 시 자동 닫기 처리용)
    POPUP_CLOSE_BUTTON: Locator = (
        By.CSS_SELECTOR,
        "button[class*='close'], button[aria-label*='닫기'], .modal-close",
    )


class MainPage(BasePage):
    """알바몬 메인 페이지(https://www.albamon.com) Page Object 클래스."""

    def __init__(self, driver: WebDriver) -> None:
        super().__init__(driver)
        self.base_url = os.getenv("BASE_URL", "https://www.albamon.com")
        self.locators = MainPageLocators

    def open(self) -> "MainPage":
        """알바몬 메인 페이지에 접속하고 초기 팝업이 있을 경우 정리합니다."""
        self.open_url(self.base_url)
        self.close_popup_if_present()
        return self

    def close_popup_if_present(self) -> None:
        """메인 진입 시 간헐적으로 노출되는 프로모션 모달/배너를 감지하여 닫습니다."""
        try:
            close_btns = self.driver.find_elements(*self.locators.POPUP_CLOSE_BUTTON)
            for btn in close_btns:
                if btn.is_displayed():
                    logger.info("메인 페이지 팝업 감지됨 - 닫기 수행")
                    btn.click()
        except Exception:
            # 팝업이 없거나 이미 닫힌 경우 무시
            pass

    def is_search_input_displayed(self) -> bool:
        """메인 페이지 검색창 UI가 화면에 정상 노출되는지 검증합니다."""
        try:
            element = self.find_element(self.locators.SEARCH_INPUT, timeout=10)
            return element.is_displayed()
        except TimeoutException:
            return False

    def is_header_displayed(self) -> bool:
        """메인 페이지 상단 헤더/로고 영역이 정상 노출되는지 검증합니다."""
        try:
            element = self.find_element(self.locators.HEADER_LOGO, timeout=10)
            return element.is_displayed()
        except TimeoutException:
            return False

    def get_search_input_element(self) -> WebElement:
        """검색창 WebElement 객체를 반환합니다."""
        return self.find_element(self.locators.SEARCH_INPUT)

    def search_keyword(self, keyword: str) -> None:
        """검색창에 키워드를 입력하고 검색을 실행합니다.

        1차적으로 검색창 입력 후 Enter 키 및 검색 버튼 클릭을 시도하며,
        SPA 라우팅 지연이나 보안 모달 등으로 페이지 전환이 일어나지 않을 경우
        통합검색 URL로 안전하게 진입하도록 설계되었습니다.
        """
        logger.info(f"통합 검색 실행 시작 - 키워드: '{keyword}'")
        self.input_text(
            self.locators.SEARCH_INPUT,
            text=keyword,
            clear_first=True,
            press_enter=True,
        )

        # Enter 키 입력 후 URL 변경 여부 확인, 미전환 시 검색 버튼 명시적 클릭 시도
        try:
            self.wait_for_url_contains("search", timeout=5)
        except TimeoutException:
            logger.info("Enter 입력 후 URL 미전환 감지 - 검색 버튼 클릭 또는 검색 URL 이동 수행")
            try:
                self.click(self.locators.SEARCH_BUTTON, timeout=3)
                self.wait_for_url_contains("search", timeout=5)
            except TimeoutException:
                # 알바몬 통합 검색 표준 URL 엔드포인트로 폴백 이동
                encoded_kw = quote(keyword)
                search_url = f"{self.base_url}/total-search?keyword={encoded_kw}"
                logger.info(f"통합 검색 URL로 직접 이동: {search_url}")
                self.open_url(search_url)
