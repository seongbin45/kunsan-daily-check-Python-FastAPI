# main.py

import os
import re
import asyncio
import traceback

from contextlib import asynccontextmanager
from datetime import datetime
from typing import Optional, Dict, Any

from fastapi import FastAPI
from pydantic import BaseModel, Field
from playwright.async_api import async_playwright


# =========================
# 설정
# =========================
BASE_URL = "https://kis.kunsan.ac.kr"
LOGIN_URL = f"{BASE_URL}/login.do"

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/120.0.0.0 Safari/537.36"
)

DEFAULT_TIMEOUT_MS = 15000
DONE_FILE_PREFIX = "check_done_today_"

run_lock = asyncio.Lock()


# =========================
# 요청 모델
# =========================
class CheckRequest(BaseModel):
    user_id: str = Field(..., min_length=1)
    user_pw: str = Field(..., min_length=1)


# =========================
# 유틸
# =========================
def safe_user_key(user_id: str) -> str:
    return re.sub(r"[^0-9A-Za-z_-]", "_", user_id)


def done_file_path(user_id: str) -> str:
    return f"{DONE_FILE_PREFIX}{safe_user_key(user_id)}.txt"


def is_already_done_today(user_id: str) -> bool:

    path = done_file_path(user_id)

    if not os.path.exists(path):
        return False

    try:

        with open(path, "r", encoding="utf-8") as f:
            last_date = f.read().strip()

        return (
            last_date ==
            datetime.now().strftime("%Y-%m-%d")
        )

    except Exception:
        return False


def mark_as_done_today(user_id: str):

    path = done_file_path(user_id)

    with open(path, "w", encoding="utf-8") as f:

        f.write(
            datetime.now().strftime("%Y-%m-%d")
        )


# =========================
# 클릭 유틸
# =========================
async def try_click_by_text(
    page,
    text: str,
    exact: bool = True,
    timeout_ms: int = 3000
) -> bool:

    try:

        locator = page.get_by_text(
            text,
            exact=exact
        ).first

        await locator.wait_for(
            state="visible",
            timeout=timeout_ms
        )

        await locator.click(force=True)

        return True

    except Exception:
        return False


async def try_click_in_frames(
    page,
    text: str,
    exact: bool = True
) -> bool:

    for frame in page.frames:

        try:

            locator = frame.get_by_text(
                text,
                exact=exact
            ).first

            if await locator.count() > 0:

                await locator.click(force=True)

                return True

        except Exception:
            continue

    return False


async def wait_for_any_popup_confirm(
    page,
    timeout_sec: int = 3
) -> bool:

    end = (
        asyncio.get_event_loop().time()
        + timeout_sec
    )

    while (
        asyncio.get_event_loop().time()
        < end
    ):

        try:

            if await try_click_by_text(
                page,
                "확인",
                exact=True,
                timeout_ms=700
            ):
                return True

            if await try_click_in_frames(
                page,
                "확인",
                exact=True
            ):
                return True

        except Exception:
            pass

        await asyncio.sleep(0.3)

    return False


# =========================
# 저장 버튼 찾기
# =========================
async def find_and_click_save(page) -> bool:

    selectors = [
        "button:has-text('저장')",
        "input[value='저장']",
        "button[data-action*='save']",
        ".btn_save",
        "text=저장",
    ]

    for sel in selectors:

        try:

            loc = page.locator(sel).first

            if await loc.count() > 0:

                await loc.click(force=True)

                return True

        except Exception:
            continue

    for frame in page.frames:

        for sel in selectors:

            try:

                loc = frame.locator(sel).first

                if await loc.count() > 0:

                    await loc.click(force=True)

                    return True

            except Exception:
                continue

    return False


# =========================
# 예 버튼 찾기
# =========================
async def find_and_click_yes(page) -> bool:

    candidates = [
        "예",
        "확인",
        "OK",
        "Yes",
        "yes"
    ]

    for text in candidates:

        if await try_click_by_text(
            page,
            text,
            exact=True,
            timeout_ms=1200
        ):
            return True

        if await try_click_in_frames(
            page,
            text,
            exact=True
        ):
            return True

    return False


# =========================
# 로그인
# =========================
async def login(
    page,
    user_id: str,
    user_pw: str
):

    print("===== LOGIN START =====")

    await page.goto(
        LOGIN_URL,
        wait_until="domcontentloaded",
        timeout=30000
    )

    print("현재 URL:", page.url)

    id_input = page.locator(
        "input#id, input[name='id'], input[type='text']"
    ).first

    pw_input = page.locator(
        "input#pw, input[name='pw'], input[type='password']"
    ).first

    await id_input.wait_for(
        state="visible",
        timeout=DEFAULT_TIMEOUT_MS
    )

    await id_input.fill(user_id)

    await pw_input.fill(user_pw)

    clicked = False

    for sel in [
        "#loginBtn",
        "button:has-text('로그인')",
        "input[value='로그인']"
    ]:

        try:

            loc = page.locator(sel).first

            if await loc.count() > 0:

                print("로그인 버튼:", sel)

                await loc.click(force=True)

                clicked = True

                break

        except Exception:
            continue

    if not clicked:

        print("엔터 로그인 시도")

        await page.keyboard.press("Enter")

    await asyncio.sleep(3)

    await wait_for_any_popup_confirm(
        page,
        timeout_sec=3
    )

    print("로그인 후 URL:", page.url)

    for _ in range(20):

        if "login.do" not in page.url:
            return

        await asyncio.sleep(0.5)

    raise RuntimeError("로그인 실패")


# =========================
# 통합정보 이동
# =========================
async def open_main_portal(page):

    print("===== 통합정보 이동 =====")

    clicked = await try_click_by_text(
        page,
        "통합정보",
        exact=True,
        timeout_ms=8000
    )

    if not clicked:

        clicked = await try_click_in_frames(
            page,
            "통합정보",
            exact=True
        )

    print("통합정보 클릭 결과:", clicked)

    if not clicked:

        raise RuntimeError(
            "'통합정보' 메뉴를 찾지 못했습니다."
        )

    await asyncio.sleep(5)

    print("통합정보 이동 후 URL:", page.url)

    return page


# =========================
# 메뉴 이동
# =========================
async def navigate_to_daily_check(page):

    print("===== 메뉴 이동 =====")

    print("현재 URL:", page.url)

    print("frame 개수:", len(page.frames))

    for idx, frame in enumerate(page.frames):

        print(
            f"FRAME[{idx}] URL:",
            frame.url
        )

    steps = [
        "학생서비스",
        "학생생활관",
        "일일체크신청"
    ]

    for step in steps:

        print(f"메뉴 이동 시도: {step}")

        clicked = await try_click_by_text(
            page,
            step,
            exact=True,
            timeout_ms=5000
        )

        if not clicked:

            clicked = await try_click_in_frames(
                page,
                step,
                exact=True
            )

        print(f"{step} 클릭 결과:", clicked)

        if not clicked:

            raise RuntimeError(
                f"'{step}' 메뉴를 찾지 못했습니다."
            )

        await asyncio.sleep(2)


# =========================
# 로그아웃
# =========================
async def logout(page):

    print("===== 로그아웃 =====")

    clicked = await try_click_by_text(
        page,
        "로그아웃",
        exact=True,
        timeout_ms=4000
    )

    if not clicked:

        clicked = await try_click_in_frames(
            page,
            "로그아웃",
            exact=True
        )

    print("로그아웃 클릭 결과:", clicked)

    if not clicked:
        return

    await asyncio.sleep(1)

    await wait_for_any_popup_confirm(
        page,
        timeout_sec=3
    )


# =========================
# 메인 실행
# =========================
async def run_daily_check(
    user_id: str,
    user_pw: str
) -> Dict[str, Any]:

    if is_already_done_today(user_id):

        return {
            "ok": True,
            "status": "skipped",
            "message": "오늘 이미 완료됨",
            "detail": {
                "user_id": user_id
            }
        }

    async with async_playwright() as p:

        browser = await p.chromium.launch(
            headless=True,
            args=[
                "--no-sandbox",
                "--disable-dev-shm-usage",
                "--disable-gpu",
                "--disable-blink-features=AutomationControlled",
                "--disable-web-security",
                "--disable-features=IsolateOrigins,site-per-process"
            ]
        )

        context = await browser.new_context(
            java_script_enabled=True,
            user_agent=USER_AGENT,
            viewport={
                "width": 1280,
                "height": 900
            }
        )

        page = await context.new_page()

        try:

            print("===== RUN START =====")

            # 로그인
            await login(
                page,
                user_id,
                user_pw
            )

            # 통합정보
            page = await open_main_portal(page)

            # 메뉴 이동
            await navigate_to_daily_check(page)

            # 저장
            save_clicked = await find_and_click_save(page)

            print("저장 버튼 결과:", save_clicked)

            if not save_clicked:

                raise RuntimeError(
                    "'저장' 버튼을 찾지 못했습니다."
                )

            await asyncio.sleep(2)

            # 예 버튼
            success_yes = False

            for _ in range(6):

                success_yes = (
                    await find_and_click_yes(page)
                )

                if success_yes:
                    break

                await asyncio.sleep(0.8)

            print("예 버튼 결과:", success_yes)

            if not success_yes:

                raise RuntimeError(
                    "최종 확인('예') 버튼을 찾지 못했습니다."
                )

            await asyncio.sleep(2)

            # 닫기
            await try_click_by_text(
                page,
                "닫기",
                exact=True,
                timeout_ms=3000
            )

            await try_click_in_frames(
                page,
                "닫기",
                exact=True
            )

            # 로그아웃
            await logout(page)

            mark_as_done_today(user_id)

            print("===== RUN SUCCESS =====")

            return {
                "ok": True,
                "status": "success",
                "message": "일일체크 완료",
                "detail": {
                    "user_id": user_id,
                    "date": datetime.now().strftime("%Y-%m-%d"),
                    "url": page.url
                }
            }

        except Exception as e:

            error_text = traceback.format_exc()

            print("===== ERROR START =====")
            print(error_text)
            print("===== ERROR END =====")

            try:

                ts = datetime.now().strftime(
                    "%Y%m%d_%H%M%S"
                )

                screenshot_path = (
                    f"daily_check_error_"
                    f"{safe_user_key(user_id)}_"
                    f"{ts}.png"
                )

                await page.screenshot(
                    path=screenshot_path,
                    full_page=True
                )

                print("스크린샷 저장:", screenshot_path)

            except Exception as screenshot_error:

                print(
                    "스크린샷 저장 실패:",
                    screenshot_error
                )

            return {
                "ok": False,
                "status": "error",
                "message": str(e),
                "detail": {
                    "user_id": user_id,
                    "url": page.url
                }
            }

        finally:

            print("브라우저 종료")

            await context.close()
            await browser.close()


# =========================
# FastAPI
# =========================
@asynccontextmanager
async def lifespan(app: FastAPI):
    yield


app = FastAPI(
    title="Daily Check API",
    version="1.0.0",
    lifespan=lifespan
)


@app.get("/")
async def root():

    return {
        "ok": True,
        "message": "Daily Check API Running"
    }


@app.get("/health")
async def health():

    return {
        "ok": True,
        "status": "healthy"
    }


# =========================
# API
# =========================
@app.post("/api/check")
async def api_check(req: CheckRequest):

    print("===== API REQUEST START =====")
    print("user_id:", req.user_id)
    print("===== API REQUEST END =====")

    try:

        async with run_lock:

            result = await run_daily_check(
                req.user_id,
                req.user_pw
            )

        print("===== API RESULT =====")
        print(result)

        return result

    except Exception as e:

        error_text = traceback.format_exc()

        print("===== API ERROR =====")
        print(error_text)

        return {
            "ok": False,
            "status": "server_error",
            "message": str(e)
        }


# =========================
# 실행
# =========================
# uvicorn main:app --host 0.0.0.0 --port 10000
