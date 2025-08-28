from fastapi import FastAPI
from pydantic import BaseModel
import subprocess

app = FastAPI()

@app.get("/")
def read_root():
    return {"message": "Hello CodeHelper!"}

# 1) 요청 바디 정의
class CodeRequest(BaseModel):
    code: str

# 2) 코드 실행 엔드포인트
@app.post("/run")
def run_code(request: CodeRequest):
    try:
        # python 실행: -c 옵션으로 전달받은 코드 실행
        result = subprocess.run(
            ["python", "-c", request.code],
            capture_output=True,
            text=True,
            timeout=5   # 무한루프 방지
        )
        return {
            "stdout": result.stdout,
            "stderr": result.stderr,
            "returncode": result.returncode
        }
    except subprocess.TimeoutExpired:
        return {"error": "Execution timed out"}