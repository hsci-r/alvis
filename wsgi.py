import os
import pymysql
from flask import Flask, Response, request


application = Flask(__name__)


PAGE_TEMPLATE = '''
<html>
<head>
<style>
body {
  font-family: arial;
}
.text {
  max-width: 450px;
  text-align: right;
  padding: 10px;
}
</style>
</head>
<body>
{{ body }}
</body>
</html>
'''

MYSQL_PARAMS = {
    'host' : os.getenv('DB_HOST'),
    'port' : int(os.getenv('DB_PORT')),
    'user' : os.getenv('DB_USER'),
    'password' : os.getenv('DB_PASS'),
    'database' : os.getenv('DB_NAME')
}


def get_text(db, doc_id):
    db.execute('SELECT pos, text FROM texts NATURAL JOIN documents WHERE title = %s;', doc_id)
    return dict(db.fetchall())


@application.route('/')
def show_index():
    result = []
    result.append('''
        <p>This is a demo of text alignment based on sentence embeddings
        provided by SentenceBERT models. The <b>matrix-align</b> algorithm
        is used to efficiently compute similarity and aligment for all
        pairs of texts. The pairs that exceed a predefined threshold
        are stored in the database.</p>
    ''')
    result.append('<p><b>Choose dataset:</b>')
    result.append('<ul>')
    with pymysql.connect(**MYSQL_PARAMS).cursor() as db:
        db.execute('SELECT name FROM collections;')
        for (name,) in db.fetchall():
            result.append('<li><a href="/sims?ds={}">{}</a>'.format(name, name))
    result.append('</ul></p>')
    return PAGE_TEMPLATE.replace('{{ body }}', '\n'.join(result))


@application.route('/sims')
def show_sims():
    global sims
    ds = request.args.get('ds', None, str)
    result = []
    result.append('<table>')
    result.append('<tr><th>doc_id_5</th><th>doc_id_2</th><th>sim_raw</th>'
                  '<th>sim_l</th><th>sim_r</th><th>sim</th></tr>')
    with pymysql.connect(**MYSQL_PARAMS).cursor() as db:
        db.execute(
            'SELECT d1.title, d2.title, s.sim_raw, s.sim_al_l, s.sim_al_r, s.sim_al'
            '  FROM sims s'
            '    JOIN documents d1 ON s.d1_id = d1.d_id'
            '    JOIN collections c1 ON d1.col_id = c1.col_id'
            '    JOIN documents d2 ON s.d2_id = d2.d_id'
            '    JOIN collections c2 ON d2.col_id = c2.col_id'
            '  WHERE c1.name = %s AND c2.name = %s'
            '  ORDER BY s.sim_raw DESC;', (ds, ds))
        for row in db.fetchall():
            result.append(
                '<tr><td>{}</td><td>{}</td><td>'
                '<a href="/diff?ds={}&doc_id_1={}&doc_id_2={}">{:.3}</a></td>'
                '<td>{:.3} %</td><td>{:.3} %</td><td>{:.3} %</td></tr>'\
                .format(row[0], row[1], ds, row[0], row[1],
                        row[2], row[3]*100, row[4]*100, row[5]*100))
    result.append('</table>')
    return PAGE_TEMPLATE.replace('{{ body }}', '\n'.join(result))


@application.route('/diff')
def show_diff():
    ds = request.args.get('ds', None, str)
    doc_id_1 = request.args.get('doc_id_1', None, str)
    doc_id_2 = request.args.get('doc_id_2', None, str)
    ROW = '<tr><td class="text"><sup>{} </sup>{}</td>'\
          '<td class="text"><sup>{} </sup>{}</td><td>{:.3}</td></tr>'
    result = []
    result.append('<table>')
    result.append('<tr><th class="text">{}</th><th class="text">{}</th>'
                  '<th>sim</th></tr>'.format(doc_id_1, doc_id_2))
    with pymysql.connect(**MYSQL_PARAMS).cursor() as db:
        db.execute(
            'SELECT a.pos1, a.pos2, a.sim '
            '  FROM als a'
            '    JOIN documents d1 ON a.d1_id = d1.d_id '
            '    JOIN texts t1 ON a.d1_id = t1.d_id AND a.pos1 = t1.pos '
            '    JOIN documents d2 ON a.d2_id = d2.d_id '
            '    JOIN texts t2 ON a.d2_id = t2.d_id AND a.pos2 = t2.pos '
            '  WHERE d1.title = %s AND d2.title = %s;', (doc_id_1, doc_id_2))
        al = list(db.fetchall())
        text_1 = get_text(db, doc_id_1)
        text_2 = get_text(db, doc_id_2)
        min_pos_1 = min(text_1.keys())
        min_pos_2 = min(text_2.keys())
        max_pos_1 = max(text_1.keys())
        max_pos_2 = max(text_2.keys())
        i, j = min_pos_1, min_pos_2
        while i <= max_pos_1 or j <= max_pos_2:
            if (not al and i <= max_pos_1) or (al and i < al[0][0]):
                result.append(ROW.format(i, text_1[i], '', '', ''))
                i += 1
                continue
            if (not al and j <= max_pos_2) or (al and j < al[0][1]):
                result.append(ROW.format('', '', j, text_2[j], ''))
                j += 1
                continue
            if al:
                result.append(ROW.format(i, text_1[i], j, text_2[j], al[0][2]))
                al.pop(0)
                i += 1
                j += 1
    result.append('</table>')
    return PAGE_TEMPLATE.replace('{{ body }}', '\n'.join(result))


if __name__ == '__main__':
    application.run()


