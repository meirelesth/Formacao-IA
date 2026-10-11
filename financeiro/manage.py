import argparse
import getpass
import json
import sqlite3
from financeiro.app import Application

p=argparse.ArgumentParser();p.add_argument('command',choices=['owner','import','backup']);p.add_argument('--file');args=p.parse_args()
app=Application()
if args.command=='owner':
    password=getpass.getpass('Crie sua senha privada (mínimo 12 caracteres): ')
    if password!=getpass.getpass('Confirme a senha: '):raise SystemExit('As senhas são diferentes.')
    app.owner('Luís Fernando',password);print('Conta privada ativada. A senha não foi gravada em texto.')
elif args.command=='import':
    records=json.load(open(args.file,encoding='utf-8'))
    with app.db() as db:
        for name in sorted({r['card_name'] for r in records if r.get('card_name')}):
            # Placeholder days never establish a historical due date; card config must be reviewed.
            db.execute('INSERT OR IGNORE INTO cards(name,closing_day,due_day,configured) VALUES(?,1,1,0)',(name,))
        imported=0
        for r in records:
            card=db.execute('SELECT id FROM cards WHERE name=?',(r.get('card_name'),)).fetchone()
            cur=db.execute('INSERT OR IGNORE INTO entries(description,kind,category,month,due_date,amount,paid,card_id,invoice_month,review,source,notes,created) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)',(r['description'],r['kind'],r['category'],r['month'],r.get('due_date'),r['amount'],r['paid'],card['id'] if card else None,r['month'] if card else None,r['review'],r['source'],r['notes'],r['created']))
            imported+=cur.rowcount
        app.audit(db,'import',detail=str(imported))
    print(f'{imported} registros importados. Replicar a importação não duplica lançamentos.')
else:
    if not args.file:raise SystemExit('Informe --file para o backup.')
    with app.db() as source,sqlite3.connect(args.file) as target:source.backup(target)
    print('Backup consistente concluído.')
