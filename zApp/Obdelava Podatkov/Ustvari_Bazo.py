import subprocess

for file in ['Pridobi_Imena.py', 'Pridobi_Sezone.py', 'Pridobi_Tekma.py']:
    path = f'zApp\Obdelava Podatkov\{file}'
    print(f"Zaganjam {file}.")
    subprocess.run(["python", path])  

print('Baza ustvarjena!')