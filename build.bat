@echo off
echo ========================================
echo  NurseScheduler .exe 빌드
echo ========================================
echo.

pip install -r requirements.txt
echo.

pyinstaller --onefile --windowed --name NurseScheduler main.py
echo.

echo 빌드 완료! dist\NurseScheduler.exe 를 확인하세요.
pause
