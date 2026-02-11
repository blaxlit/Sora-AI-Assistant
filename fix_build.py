import flet
import os

# หาที่อยู่จริงของ Flet ในเครื่องคุณ
flet_path = os.path.dirname(flet.__file__)
bin_path = os.path.join(flet_path, "bin")

# สร้างคำสั่ง PyInstaller ที่ถูกต้องให้
print("-" * 50)
print("✅ COPY คำสั่งข้างล่างนี้ไปใช้แทนอันเดิมครับ:")
print("-" * 50)
print(f'pyinstaller --name SoraAI --onefile --noconsole --add-data "{bin_path}{os.pathsep}flet/bin" main.py')
print("-" * 50)