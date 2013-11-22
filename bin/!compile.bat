cd ..
python setup.py bdist_egg
move dist\* .
rd /s /q dist
pause
