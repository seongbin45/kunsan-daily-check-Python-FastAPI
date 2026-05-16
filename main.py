# ==================================================
# main.py
# ==================================================

import asyncio
import traceback

from datetime import datetime
from typing import Dict, Any

from fastapi import FastAPI
from pydantic import BaseModel, Field

from playwright.async_api import async_playwright


# ==================================================
# FastAPI
# ==================================================
app = FastAPI(
    title="Kunsan Daily Check API",
    version="7.0.0"
)


# ==================================================
# 설정
# ==================================================
LOGIN_URL = "https://kis.kunsan.ac.kr/login.do"

run_lock = asyncio.Lock()


# ==================================================
# 요청 모델
# ==================================================
class CheckRequest(BaseModel):

    user_id: str = Field(..., min_length=1)

    user_pw: str = Field(..., min_length=1)


# ==================================================
# ROOT
# ==================================================
@app.get("/")
async def root():

    return {
        "ok": True,
        "message": "Kunsan Daily Check API Running"
    }


# ==================================================
# HEALTH
# ==================================================
@app.get("/health")
async def health():

    return {
        "ok": True,
        "status": "healthy"
    }


# ==================================================
# Dialog 자동 처리
# ==================================================
async def handle_dialog(dialog):

    try:

        print(
            f"[Dialog 감지] {dialog.message}"
        )

        await dialog.accept()

        print(
            "[Dialog 자동 승인 완료]"
        )

    except Exception as e:

        print(
            f"Dialog 처리 실패: {e}"
        )


# ==================================================
# 실제 완료 검증
# ==================================================
async def verify_daily_check(new_tab) -> bool:

    try:

        print("================================================")
        print("실제 체크 완료 검증 시작")
        print("================================================")

        await asyncio.sleep(5)

        body_text = await new_tab.locator(
            "body"
        ).inner_text()

        keywords = [
            "체크완료",
            "완료",
            "신청완료"
        ]

        for keyword in keywords:

            if keyword in body_text:

                print(
                    f"[검증 성공] {keyword}"
                )

                return True

        print(
            "[검증 실패] 완료 문구 미검출"
        )

        return False

    except Exception as e:

        print(
            f"검증 중 오류 발생: {e}"
        )

        return False


# ==================================================
# 메인 자동화
# ==================================================
async def perform_check(
    user_id: str,
    user_pw: str
) -> Dict[str, Any]:

    async with async_playwright() as p:

        browser = await p.chromium.launch(

            # ==================================================
            # Render 서버에서는 headless=True 권장
            # 로컬 디버깅 시 False 추천
            # ==================================================
            headless=True,

            slow_mo=1000,

            args=[
                "--no-sandbox",
                "--disable-dev-shm-usage",
                "--disable-gpu",
                "--disable-setuid-sandbox",
                "--disable-blink-features=AutomationControlled",
                "--disable-web-security",
                "--disable-features=IsolateOrigins,site-per-process"
            ]
        )

        context = await browser.new_context(

            viewport={
                "width": 1280,
                "height": 800
            },

            java_script_enabled=True,

            user_agent=(
                "Mozilla/5.0 "
                "(Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 "
                "(KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            )
        )

        page = await context.new_page()

        # ==================================================
        # dialog 자동 처리 연결
        # ==================================================
        page.on(
            "dialog",
            handle_dialog
        )

        try:

            # ==================================================
            # 로그인 페이지 접속
            # ==================================================
            print("================================================")
            print("1. 로그인 페이지 접속")
            print("================================================")

            await page.goto(
                LOGIN_URL,
                wait_until="networkidle",
                timeout=60000
            )

            # ==================================================
            # 로그인 입력
            # ==================================================
            try:

                id_input = page.locator(
                    "input#id, input[name='id'], input[type='text']"
                ).first

                await id_input.wait_for(
                    state="visible",
                    timeout=15000
                )

                await id_input.fill(user_id)

                pw_input = page.locator(
                    "input#pw, input[name='pw'], input[type='password']"
                ).first

                await pw_input.fill(user_pw)

                print(
                    "로그인 정보 입력 완료"
                )

                await page.keyboard.press(
                    "Enter"
                )

            except Exception as e:

                raise RuntimeError(
                    f"로그인 입력 실패: {e}"
                )

            # ==================================================
            # 중복 로그인 팝업 처리
            # ==================================================
            try:

                await asyncio.sleep(2)

                confirm_btn = page.get_by_role(
                    "button",
                    name="확인"
                )

                if await confirm_btn.is_visible(
                    timeout=3000
                ):

                    await confirm_btn.click()

                    print(
                        "중복 로그인 확인 클릭"
                    )

            except Exception:
                pass

            # ==================================================
            # 통합정보 이동
            # ==================================================
            print("================================================")
            print("2. 통합정보 새 창 이동")
            print("================================================")

            await asyncio.sleep(2)

            try:

                async with context.expect_page() as new_page_info:

                    await page.get_by_text(
                        "통합정보"
                    ).first.click()

                new_tab = await new_page_info.value

                new_tab.on(
                    "dialog",
                    handle_dialog
                )

                await new_tab.wait_for_load_state(
                    "networkidle"
                )

                print(
                    "새 창 전환 성공"
                )

            except Exception as e:

                raise RuntimeError(
                    f"통합정보 이동 실패: {e}"
                )

            # ==================================================
            # 학생서비스
            # ==================================================
            print("================================================")
            print("3. 학생서비스 클릭")
            print("================================================")

            await new_tab.get_by_text(
                "학생서비스"
            ).first.click()

            await asyncio.sleep(2)

            # ==================================================
            # MY MENU
            # ==================================================
            print("================================================")
            print("4. MY MENU 진입")
            print("================================================")

            await asyncio.sleep(3)

            await new_tab.get_by_text(
                "MY MENU"
            ).first.click()

            await asyncio.sleep(1)

            # ==================================================
            # 일일체크신청
            # ==================================================
            print("================================================")
            print("5. 일일체크신청 클릭")
            print("================================================")

            await new_tab.get_by_text(
                "일일체크신청"
            ).last.click()

            await asyncio.sleep(3)

            # ==================================================
            # 저장 버튼 클릭
            # ==================================================
            print("================================================")
            print("6. 저장 버튼 클릭 시도")
            print("================================================")

            found = False

            try:

                save_button = new_tab.locator(
                    "button:has-text('저장'), input[value='저장'], .btn_save"
                ).first

                await save_button.wait_for(
                    state="visible",
                    timeout=15000
                )

                await save_button.click(
                    force=True
                )

                print(
                    "저장 버튼 클릭 성공"
                )

                found = True

            except Exception:

                print(
                    "일반 방식 실패 → 프레임 탐색 시작"
                )

                for frame in new_tab.frames:

                    try:

                        target = (
                            frame
                            .get_by_role(
                                "button",
                                name="저장"
                            )
                            .or_(
                                frame.locator(
                                    "text='저장'"
                                )
                            )
                        )

                        if await target.count() > 0:

                            await target.first.click(
                                force=True
                            )

                            print(
                                "프레임 내부 저장 버튼 클릭 성공"
                            )

                            found = True

                            break

                    except Exception:
                        continue

            if not found:

                raise RuntimeError(
                    "저장 버튼을 찾지 못했습니다."
                )

            # ==================================================
            # 처리 대기
            # ==================================================
            print("================================================")
            print("7. 처리 대기")
            print("================================================")

            await asyncio.sleep(2)

            # ==================================================
            # Enter 입력
            # ==================================================
            try:

                await new_tab.keyboard.press(
                    "Enter"
                )

                print(
                    "Enter 입력 완료"
                )

            except Exception:
                pass

            await asyncio.sleep(1)

            # ==================================================
            # 추가 팝업 처리
            # ==================================================
            final_success = False

            for _ in range(5):

                for frame in new_tab.frames:

                    try:

                        btns = frame.locator(
                            """
                            button,
                            input[type='button'],
                            input[type='submit'],
                            a.btn
                            """
                        )

                        count = await btns.count()

                        for i in range(count):

                            target = btns.nth(i)

                            txt = await target.inner_text()

                            val = (
                                await target.get_attribute(
                                    "value"
                                ) or ""
                            )

                            total_text = txt + val

                            if any(
                                x in total_text
                                for x in [
                                    "예",
                                    "확인",
                                    "OK",
                                    "yes"
                                ]
                            ):

                                await target.click(
                                    force=True
                                )

                                print(
                                    f"추가 팝업 처리 완료: {total_text}"
                                )

                                final_success = True

                                break

                    except Exception:
                        continue

                if final_success:
                    break

                await asyncio.sleep(0.5)

            # ==================================================
            # 로그아웃 처리
            # ==================================================
            print("================================================")
            print("8. 로그아웃 처리")
            print("================================================")

            try:

                target_element = None

                for frame in new_tab.frames:

                    try:

                        el = frame.get_by_text(
                            "로그아웃"
                        ).first

                        if (
                            await el.count() > 0 and
                            await el.is_visible()
                        ):

                            target_element = el

                            print(
                                f"[{frame.name or '프레임'}] 로그아웃 버튼 발견"
                            )

                            break

                    except Exception:
                        continue

                if target_element:

                    box = await target_element.bounding_box()

                    if box:

                        center_x = (
                            box["x"] +
                            box["width"] / 2
                        )

                        center_y = (
                            box["y"] +
                            box["height"] / 2
                        )

                        await new_tab.mouse.move(
                            center_x,
                            center_y
                        )

                        await new_tab.mouse.click(
                            center_x,
                            center_y
                        )

                        print(
                            "좌표 기반 로그아웃 클릭 완료"
                        )

                else:

                    print(
                        "로그아웃 버튼 미검출 → 우측 상단 강제 클릭"
                    )

                    await new_tab.mouse.click(
                        1150,
                        40
                    )

            except Exception as e:

                print(
                    f"로그아웃 처리 실패: {e}"
                )

            # ==================================================
            # 세션 종료 대기
            # ==================================================
            print("================================================")
            print("9. 세션 종료 대기")
            print("================================================")

            await asyncio.sleep(5)

            # ==================================================
            # 실제 완료 검증
            # ==================================================
            verified = await verify_daily_check(
                new_tab
            )

            if not verified:

                raise RuntimeError(
                    "저장은 눌렸지만 실제 완료 검증 실패"
                )

            # ==================================================
            # 최종 종료
            # ==================================================
            print("================================================")
            print("SUCCESS")
            print("================================================")

            return {

                "ok": True,

                "status": "success",

                "message": "일일체크 완료",

                "detail": {

                    "user_id": user_id,

                    "date": datetime.now().strftime(
                        "%Y-%m-%d %H:%M:%S"
                    )
                }
            }

        except Exception as e:

            print("================================================")
            print("ERROR")
            print("================================================")

            print(
                traceback.format_exc()
            )

            try:

                screenshot_name = (
                    f"error_"
                    f"{datetime.now().strftime('%Y%m%d_%H%M%S')}"
                    f".png"
                )

                await page.screenshot(
                    path=screenshot_name,
                    full_page=True
                )

                print(
                    f"스크린샷 저장 완료: {screenshot_name}"
                )

            except Exception:
                pass

            return {

                "ok": False,

                "status": "error",

                "message": str(e)
            }

        finally:

            await context.close()

            await browser.close()


# ==================================================
# API
# ==================================================
@app.post("/api/check")
async def api_check(req: CheckRequest):

    async with run_lock:

        result = await perform_check(
            req.user_id,
            req.user_pw
        )

        return result


# ==================================================
# 실행
# uvicorn main:app --host 0.0.0.0 --port 10000
# ==================================================
