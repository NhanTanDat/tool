import uiautomation as auto
import subprocess, time

# 1) Mở adobe promiere
subprocess.Popen(r"C:\Program Files\Adobe\Adobe Premiere Pro 2022\Adobe Premiere Pro.exe")

#bam nut open peoject
time.sleep(3)
filepath = r"C:\Users\phamp\OneDrive\Máy tính\Untitled.prproj"
auto.SendKeys('{Ctrl}o')
time.sleep(2)

auto.SendKeys(filepath)
auto.SendKeys('{Enter}')