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
    version="8.0.0"
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
# 루트
# ==================================================
@app.get("/")
async def root():

    return {
        "ok": True,
        "message": "Kunsan Daily Check API Running"
    }


@app.get("/health")
async def health():

    return {
        "ok": True,
        "status": "healthy"
    }


# ==================================================
# 실제 완료 검증
# iframe 전체 탐색 기반
# ==================================================
async def verify_daily_check(
    new_tab,
    logs
) -> bool:

    verify_keywords = [
        "체크완료",
        "신청완료",
        "정상처리",
        "처리되었습니다",
        "이미 신청"
    ]

    try:

        logs.append(
            "실제 완료 여부 검증 시작"
        )

        print("================================================")
        print("실제 완료 검증 시작")
        print("================================================")

        await asyncio.sleep(5)

        # ==================================================
        # 메인 body 검사
        # ==================================================
        try:

            body_text = await new_tab.locator(
                "body"
            ).inner_text()

            for keyword in verify_keywords:

                if keyword in body_text:

                    print(
                        f"[검증 성공] MAIN BODY → {keyword}"
                    )

                    logs.append(
                        f"완료 검증 성공: {keyword}"
                    )

                    return True

        except Exception:
            pass

        # ==================================================
        # iframe 전체 검사
        # ==================================================
        for frame in new_tab.frames:

            try:

                frame_text = await frame.locator(
                    "body"
                ).inner_text()

                for keyword in verify_keywords:

                    if keyword in frame_text:

                        print(
                            f"[검증 성공] FRAME → {keyword}"
                        )

                        logs.append(
                            f"완료 검증 성공: {keyword}"
                        )

                        return True

            except Exception:
                continue

        # ==================================================
        # 실패
        # ==================================================
        print("완료 문구 검출 실패")

        logs.append(
            "완료 문구 검출 실패"
        )

        return False

    except Exception as e:

        print("검증 실패:", e)

        logs.append(
            f"검증 실패: {str(e)}"
        )

        return False


# ==================================================
# 메인 자동화
# ==================================================
async def perform_check(
    user_id: str,
    user_pw: str
) -> Dict[str, Any]:

    logs = []

    async with async_playwright() as p:

        browser = await p.chromium.launch(
            headless=True,
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

        try:

            # ==================================================
            # 로그인
            # ==================================================
            print("1. 로그인 페이지 접속")

            logs.append(
                "로그인 페이지 접속"
            )

            await page.goto(
                LOGIN_URL,
                wait_until="networkidle"
            )

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

            print("로그인 정보 입력 완료")

            logs.append(
                "로그인 성공"
            )

            await page.keyboard.press(
                "Enter"
            )

            # ==================================================
            # 중복 로그인 팝업
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

                    logs.append(
                        "중복 로그인 팝업 처리"
                    )

            except Exception:
                pass

            # ==================================================
            # 통합정보 이동
            # ==================================================
            print("2. 통합정보 이동")

            logs.append(
                "통합정보 페이지 이동 시도"
            )

            await asyncio.sleep(2)

            async with context.expect_page() as new_page_info:

                await page.get_by_text(
                    "통합정보"
                ).first.click()

            new_tab = await new_page_info.value

            await new_tab.wait_for_load_state(
                "networkidle"
            )

            print("새 창 전환 성공")

            logs.append(
                "통합정보 이동 성공"
            )

            # ==================================================
            # 학생서비스
            # ==================================================
            print("3. 학생서비스 클릭")

            logs.append(
                "학생서비스 진입"
            )

            await new_tab.get_by_text(
                "학생서비스"
            ).first.click()

            await asyncio.sleep(2)

            # ==================================================
            # MY MENU
            # ==================================================
            print("4. MY MENU 진입")

            logs.append(
                "MY MENU 진입"
            )

            await asyncio.sleep(3)

            await new_tab.get_by_text(
                "MY MENU"
            ).first.click()

            await asyncio.sleep(1)

            # ==================================================
            # 일일체크신청
            # ==================================================
            print("5. 일일체크 메뉴 클릭")

            logs.append(
                "일일체크 메뉴 클릭"
            )

            await new_tab.get_by_text(
                "일일체크신청"
            ).last.click()

            await asyncio.sleep(3)

            # ==================================================
            # 저장 버튼 클릭
            # ==================================================
            print("6. 저장 버튼 클릭 시도")

            logs.append(
                "저장 버튼 탐색 시작"
            )

            save_clicked = False

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

                await asyncio.sleep(3)

                save_clicked = True

                print(
                    "저장 버튼 클릭 성공"
                )

                logs.append(
                    "저장 버튼 클릭 성공"
                )

            except Exception:

                print(
                    "일반 저장 버튼 실패 → 프레임 탐색"
                )

                logs.append(
                    "프레임 내부 저장 버튼 탐색"
                )

                for frame in new_tab.frames:

                    try:

                        target = frame.get_by_role(
                            "button",
                            name="저장"
                        ).or_(
                            frame.locator(
                                "text='저장'"
                            )
                        )

                        if await target.count() > 0:

                            await target.first.click()

                            save_clicked = True

                            print(
                                "프레임 저장 버튼 클릭 성공"
                            )

                            logs.append(
                                "프레임 저장 버튼 클릭 성공"
                            )

                            break

                    except Exception:
                        continue

            if not save_clicked:

                logs.append(
                    "저장 버튼 탐색 실패"
                )

                raise RuntimeError(
                    "저장 버튼을 찾지 못했습니다."
                )

            # ==================================================
            # 저장 반영 대기
            # ==================================================
            await asyncio.sleep(3)

            # ==================================================
            # 추가 팝업 처리
            # ==================================================
            print("7. 추가 팝업 처리")

            logs.append(
                "추가 팝업 처리 시작"
            )

            await asyncio.sleep(2)

            final_success = False

            # ==================================================
            # 원본 코드 유지
            # Enter 강제 입력
            # ==================================================
            await new_tab.keyboard.press(
                "Enter"
            )

            await asyncio.sleep(1)

            for _ in range(5):

                for frame in new_tab.frames:

                    try:

                        btns = frame.locator(
                            "button, input[type='button'], input[type='submit'], a.btn"
                        )

                        count = await btns.count()

                        for i in range(count):

                            target = btns.nth(i)

                            txt = await target.inner_text()

                            val = await target.get_attribute(
                                "value"
                            ) or ""

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

                                logs.append(
                                    f"추가 팝업 처리: {total_text}"
                                )

                                final_success = True

                                break

                    except Exception:
                        continue

                if final_success:
                    break

                await asyncio.sleep(0.5)

            # ==================================================
            # 닫기 단계
            # 원본 흐름 최대한 유지
            # ==================================================
            print("8. 닫기 단계")

            logs.append(
                "닫기 단계 진입"
            )

            try:

                await new_tab.keyboard.press(
                    "Enter"
                )

                await asyncio.sleep(2)

                logs.append(
                    "닫기 Enter 입력 완료"
                )

            except Exception:
                pass

            # ==================================================
            # 세션 반영 대기
            # ==================================================
            print("9. 세션 반영 대기")

            logs.append(
                "서버 반영 대기 중"
            )

            await asyncio.sleep(5)

            # ==================================================
            # 실제 완료 검증
            # ==================================================
            verified = await verify_daily_check(
                new_tab,
                logs
            )

            if not verified:

                raise RuntimeError(
                    "저장은 눌렸지만 실제 완료 여부를 확인하지 못했습니다."
                )

            # ==================================================
            # 로그아웃
            # ==================================================
            try:

                print("10. 로그아웃 시도")

                logs.append(
                    "로그아웃 시도"
                )

                new_tab.on(
                    "dialog",
                    lambda dialog:
                    dialog.accept()
                )

                target_element = None

                for frame in new_tab.frames:

                    try:

                        el = frame.get_by_text(
                            "로그아웃"
                        ).first

                        if (
                            await el.count() > 0
                            and
                            await el.is_visible()
                        ):

                            target_element = el

                            break

                    except Exception:
                        continue

                if target_element:

                    box = await target_element.bounding_box()

                    if box:

                        center_x = (
                            box['x'] +
                            box['width'] / 2
                        )

                        center_y = (
                            box['y'] +
                            box['height'] / 2
                        )

                        await new_tab.mouse.move(
                            center_x,
                            center_y
                        )

                        await new_tab.mouse.click(
                            center_x,
                            center_y
                        )

                        logs.append(
                            "로그아웃 완료"
                        )

                else:

                    await new_tab.mouse.click(
                        1150,
                        40
                    )

                    logs.append(
                        "강제 로그아웃 클릭"
                    )

            except Exception as e:

                logs.append(
                    f"로그아웃 실패: {str(e)}"
                )

            # ==================================================
            # 완료
            # ==================================================
            print("SUCCESS")

            logs.append(
                "전체 작업 완료"
            )

            return {
                "ok": True,
                "status": "success",
                "message": "일일체크 완료",
                "logs": logs,
                "detail": {
                    "user_id": user_id,
                    "date": datetime.now().strftime(
                        "%Y-%m-%d %H:%M:%S"
                    )
                }
            }

        except Exception as e:

            print("ERROR")
            print(traceback.format_exc())

            logs.append(
                f"오류 발생: {str(e)}"
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

                logs.append(
                    f"스크린샷 저장: {screenshot_name}"
                )

            except Exception:
                pass

            return {
                "ok": False,
                "status": "error",
                "message": str(e),
                "logs": logs
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
