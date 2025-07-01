with open('sat_names.csv', 'r', encoding='cp1252') as file:
    content = file.read()

with open('sat_names.csv', 'w', encoding='utf-8') as file:
    file.write(content)
