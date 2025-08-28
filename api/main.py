from fastapi import FastAPI
from pydantic import BaseModel
import subprocess, tempfile, os
from typing import Optional, List

app = FastAPI()

@app.get("/")
def read_root():
    return {"message": "Hello CodeHelper!"}

# ===== /run: 코드 실행 (입력/타임아웃 지원) =====
class CodeRequest(BaseModel):
    code: str
    stdin: Optional[str] = None        # 표준입력 (없으면 빈 문자열로 처리)
    timeout: Optional[float] = 5.0     # 초 단위 타임아웃 (기본 5초)

@app.post("/run")
def run_code(request: CodeRequest):
    # 코드 임시 파일 저장
    with tempfile.NamedTemporaryFile(suffix=".py", delete=False, mode="w", encoding="utf-8") as f:
        f.write(request.code)
        path = f.name
    try:
        result = subprocess.run(
            ["python", "-I", path],              # -I: 격리 모드
            input=(request.stdin or ""),
            capture_output=True,
            text=True,
            timeout=(request.timeout or 5.0)
        )
        return {
            "stdout": result.stdout,
            "stderr": result.stderr,
            "returncode": result.returncode
        }
    except subprocess.TimeoutExpired:
        return {"stdout": "", "stderr": f"Error: Timeout ({request.timeout or 5.0}s)", "returncode": -1}
    finally:
        try: os.remove(path)
        except Exception: pass


# ===== /grade: 여러 테스트케이스 채점 (입력/개별 타임아웃 지원) =====
class TestCase(BaseModel):
    input: str                    # 각 케이스에 줄 표준입력
    expected: str                 # 기대 출력(개행 포함 가능)
    timeout: Optional[float] = None  # 이 케이스만의 타임아웃(없으면 기본값 사용)

class GradeRequest(BaseModel):
    code: str
    cases: List[TestCase]
    strip_output: bool = True         # 양끝 공백/개행 무시 비교
    default_timeout: float = 2.0      # 케이스별 timeout이 없을 때 사용하는 기본 타임아웃(초)

@app.post("/grade")
def grade_code(req: GradeRequest):
    # 제출 코드를 임시 파일로 저장
    with tempfile.NamedTemporaryFile(suffix=".py", delete=False, mode="w", encoding="utf-8") as f:
        f.write(req.code)
        path = f.name

    results = []
    passed = 0

    try:
        for idx, case in enumerate(req.cases, start=1):
            t = case.timeout if case.timeout is not None else req.default_timeout
            try:
                proc = subprocess.run(
                    ["python", "-I", path],
                    input=(case.input or ""),
                    capture_output=True,
                    text=True,
                    timeout=t
                )
                out = proc.stdout
                err = proc.stderr

                # 비교 규칙
                if req.strip_output:
                    ok = (proc.returncode == 0) and (out.strip() == case.expected.strip())
                else:
                    ok = (proc.returncode == 0) and (out == case.expected)

                results.append({
                    "case": idx,
                    "input": case.input,
                    "expected": case.expected,
                    "stdout": out,
                    "stderr": err,
                    "returncode": proc.returncode,
                    "timeout_used": t,
                    "ok": ok
                })
                if ok:
                    passed += 1

            except subprocess.TimeoutExpired:
                results.append({
                    "case": idx,
                    "input": case.input,
                    "expected": case.expected,
                    "stdout": "",
                    "stderr": f"Error: Timeout ({t}s)",
                    "returncode": -1,
                    "timeout_used": t,
                    "ok": False
                })

        total = len(req.cases)
        return {
            "score": f"{passed}/{total}",
            "passed": passed,
            "total": total,
            "results": results
        }
    finally:
        try: os.remove(path)
        except Exception: pass
