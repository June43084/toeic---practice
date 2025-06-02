import pytest
import os
from datetime import datetime


def run_tests():
    # 建立報告目錄
    report_dir = "test_reports"
    if not os.path.exists(report_dir):
        os.makedirs(report_dir)

    # 生成報告檔名
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    report_path = f"{report_dir}/report_{timestamp}.html"

    # 執行測試並生成報告
    pytest.main([
        "test_app.py",
        f"--html={report_path}",
        "--self-contained-html",
        "--cov=app",
        "--cov-report=html",
        "-v"
    ])


if __name__ == "__main__":
    run_tests()