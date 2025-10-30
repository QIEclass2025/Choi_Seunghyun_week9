@echo off
echo Installing required Python packages from requirements.txt...
pip install -r requirements.txt

echo.
echo All packages installed. Starting the game...
echo.

python chess_game.py

echo.
echo The game has finished. Press any key to exit.
pause
