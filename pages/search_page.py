import logging
from typing import List

from selenium.common.exceptions import TimeoutException
from selenium.webdriver.common.by import By
from selenium.webdriver.remote.webdriver import WebDriver
from selenium.webdriver.remote.webelement import WebElement

from pages.base_page import BasePage, Locator

logger = logging.getLogger(__name__)


class SearchPageLocators:
    """알바몬 검색 결과 페이지 및 채용 공고 상세 페이지 셀렉터(Locator) 중앙 관리 클래스.

    웹사이트 구조 변경 시 이 클래스의 셀렉터만 수정하면 전체 테스트 코드에 즉시 반영됩니다.
    """

    # 검색 결과 페이지 내 채용 공고 상세 링크 리스트 (알바몬 공고 상세 URL 패턴: /jobs/detail/{id})
    JOB_POSTING_LINKS: Locator = (
        By.CSS_SELECTOR,
        "a[href*='/jobs/detail/'], a[href*='recruit/view'], li[class*='recruit'] a, article a[href*='jobs']",
    )

    # 검색 결과 컨테이너 영역
    SEARCH_RESULT_CONTAINER: Locator = (
        By.CSS_SELECTOR,
        "main, #__next, [class*='search'], [class*='recruit-list']",
    )

    # 공고 상세 페이지 내 핵심 검증 요소 (공고 제목, 근무조건/지원하기 영역 등)
    JOB_DETAIL_HEADER: Locator = (
        By.CSS_SELECTOR,
        "h1, h2, [class*='detail'], [class*='recruit-title'], main",
    )


class SearchPage(BasePage):
    """알바몬 검색 결과 페이지 및 공고 상세 진입 검증을 담당하는 Page Object 클래스."""

    def __init__(self, driver: WebDriver) -> None:
        super().__init__(driver)
        self.locators = SearchPageLocators

    def wait_until_loaded(self) -> "SearchPage":
        """검색 결과 페이지의 주요 컨테이너와 공고 리스트가 렌더링될 때까지 대기합니다."""
        self.wait_for_page_load()
        self.find_present_element(self.locators.SEARCH_RESULT_CONTAINER)
        return self

    def is_search_result_page(self, keyword: str | None = None) -> bool:
        """현재 페이지가 검색 결과 페이지인지 URL 또는 화면 요소로 검증합니다."""
        current_url = self.get_current_url().lower()
        is_url_valid = "search" in current_url or "keyword" in current_url or "jobs" in current_url

        if is_url_valid:
            return True

        # URL이 SPA 특성상 다르게 표현될 경우 공고 리스트 노출 여부로 보조 판단
        return self.get_job_postings_count() > 0

    def get_job_posting_elements(self) -> List[WebElement]:
        """검색 결과에 노출된 채용 공고 링크 요소 리스트를 반환합니다."""
        elements = self.find_elements(self.locators.JOB_POSTING_LINKS, timeout=15)
        # 실제 화면에 표시되고 유효한 href를 가진 공고 요소만 필터링
        valid_elements = [
            el for el in elements if el.is_displayed() and el.get_attribute("href")
        ]
        logger.info(f"탐색된 유효 채용 공고 수: {len(valid_elements)}개")
        return valid_elements

    def get_job_postings_count(self) -> int:
        """검색 결과 페이지에 노출된 채용 공고의 개수를 반환합니다."""
        return len(self.get_job_posting_elements())

    def click_first_job_posting(self) -> str:
        """검색 결과 리스트의 첫 번째 채용 공고를 클릭하여 상세 페이지로 이동합니다.

        클릭 전 첫 번째 공고의 이동 대상 URL(href)을 로깅 및 반환하며,
        새 탭으로 열리는 경우 자동으로 최신 탭으로 포커스를 전환합니다.
        """
        postings = self.get_job_posting_elements()
        if not postings:
            raise AssertionError("검색 결과에서 클릭할 수 있는 채용 공고를 찾지 못했습니다.")

        first_posting = postings[0]
        target_href = first_posting.get_attribute("href") or ""
        posting_text = first_posting.text.strip().replace("\n", " ")[:40]
        logger.info(f"첫 번째 채용 공고 클릭: '{posting_text}' (URL: {target_href})")

        initial_handles = len(self.driver.window_handles)

        try:
            # 화면 중앙으로 스크롤 후 클릭
            self.driver.execute_script(
                "arguments[0].scrollIntoView({block: 'center'});", first_posting
            )
            first_posting.click()
        except Exception as e:
            logger.warning(f"일반 클릭 예외 발생 ({e.__class__.__name__}) - JS 클릭으로 전환")
            self.driver.execute_script("arguments[0].click();", first_posting)

        # 새 탭으로 열렸을 경우 새 탭으로 포커스 전환
        if len(self.driver.window_handles) > initial_handles:
            self.switch_to_latest_window()
        else:
            # 현재 탭에서 이동하는 경우 URL 변경 대기, 미이동 시 href로 직접 이동 보장
            try:
                self.wait_for_url_contains("detail", timeout=7)
            except TimeoutException:
                if target_href.startswith("http"):
                    logger.info(f"상세 페이지 URL로 직접 이동 보장: {target_href}")
                    self.open_url(target_href)

        self.wait_for_page_load()
        return target_href

    def is_job_detail_page_loaded(self) -> bool:
        """채용 공고 상세 페이지에 정상 진입했는지 URL 패턴 및 상세 헤더 요소로 검증합니다."""
        current_url = self.get_current_url().lower()
        is_detail_url = any(
            token in current_url for token in ("/jobs/detail", "recruit", "detail", "gi_no")
        )

        try:
            header_element = self.find_element(self.locators.JOB_DETAIL_HEADER, timeout=10)
            is_header_visible = header_element.is_displayed()
        except TimeoutException:
            is_header_visible = False

        logger.info(
            f"상세 페이지 진입 검증 - URL: {self.get_current_url()} "
            f"(URL 매칭: {is_detail_url}, 상세 UI 노출: {is_header_visible})"
        )
        return is_detail_url and is_header_visible
