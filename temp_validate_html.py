from pathlib import Path
from html.parser import HTMLParser

class Parser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.errors = []

    def error(self, message):
        self.errors.append(message)

for fn in ['ml/borne.html', 'ml/salle_attente.html', 'ml/medecin.html']:
    data = Path(fn).read_text(encoding='utf-8')
    parser = Parser()
    try:
        parser.feed(data)
    except Exception as e:
        parser.errors.append(str(e))
    print(fn, 'OK' if not parser.errors else 'ERROR', parser.errors[:5])
