import os, sqlite3, csv, zipfile, datetime
from kivy.app import App
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.gridlayout import GridLayout
from kivy.uix.scrollview import ScrollView
from kivy.uix.label import Label
from kivy.uix.button import Button
from kivy.uix.textinput import TextInput
from kivy.uix.spinner import Spinner
from kivy.uix.popup import Popup
from kivy.core.window import Window
from kivy.metrics import dp

APP='EXPRESS LOCAL OS'; VERSION='V3.0.0'
BASE=os.path.dirname(os.path.abspath(__file__))
DATA=os.path.join(BASE,'data'); REL=os.path.join(BASE,'relatorios'); BKP=os.path.join(BASE,'backups')
for p in (DATA,REL,BKP): os.makedirs(p,exist_ok=True)
DB=os.path.join(DATA,'estoque_express.db')
Window.clearcolor=(0.02,0.04,0.08,1)

def fmt(n):
    try:
        f=float(n)
        return str(int(f)) if f.is_integer() else f'{f:.3f}'.rstrip('0').rstrip('.')
    except Exception: return str(n)

def today(): return datetime.datetime.now().strftime('%d/%m/%Y %H:%M')

def conn():
    c=sqlite3.connect(DB); c.row_factory=sqlite3.Row; return c

def init_db():
    with conn() as c:
        c.execute('''CREATE TABLE IF NOT EXISTS produtos(id INTEGER PRIMARY KEY AUTOINCREMENT,codigo TEXT UNIQUE,nome TEXT NOT NULL,categoria TEXT,unidade TEXT,estoque REAL DEFAULT 0,minimo REAL DEFAULT 0,localizacao TEXT,obs TEXT,ativo INTEGER DEFAULT 1,criado_em TEXT)''')
        c.execute('''CREATE TABLE IF NOT EXISTS movimentos(id INTEGER PRIMARY KEY AUTOINCREMENT,produto_id INTEGER,tipo TEXT,quantidade REAL,data_mov TEXT,turno TEXT,resp TEXT,obs TEXT,criado_em TEXT)''')
        c.execute('''CREATE TABLE IF NOT EXISTS conferencias(id INTEGER PRIMARY KEY AUTOINCREMENT,produto_id INTEGER,sistema REAL,fisico REAL,diferenca REAL,obs TEXT,criado_em TEXT)''')
        c.commit()

def executar(sql,args=(),one=False):
    with conn() as c:
        cur=c.execute(sql,args); c.commit()
        return cur.fetchone() if one else cur.fetchall()

class UI:
    @staticmethod
    def label(t,sp=16,b=False,h=None):
        return Label(text=('[b]'+t+'[/b]') if b else t, markup=True, font_size=sp, color=(0.9,0.95,1,1), size_hint_y=None, height=h or dp(34), halign='left', valign='middle')
    @staticmethod
    def btn(t,fn,bg=(0.0,0.25,0.55,1),h=72):
        b=Button(text=t, font_size=16, bold=True, background_normal='', background_color=bg, color=(1,1,1,1), size_hint_y=None, height=dp(h))
        b.bind(on_release=lambda *_: fn()); return b
    @staticmethod
    def inp(hint='',num=False):
        return TextInput(hint_text=hint, multiline=False, input_filter='float' if num else None, font_size=16, size_hint_y=None, height=dp(48), background_color=(0.94,0.96,1,1))

class ExpressApp(App):
    def build(self):
        init_db(); self.rootbox=BoxLayout(orientation='vertical', padding=dp(10), spacing=dp(8)); self.home(); return self.rootbox
    def clear(self): self.rootbox.clear_widgets(); self.header()
    def header(self):
        self.rootbox.add_widget(UI.label(f'[color=35a8ff][b]{APP} {VERSION}[/b][/color]\nGestão de Estoque Colorado — By Maicon',18,False,dp(66)))
    def popup(self,msg,title='Aviso'):
        box=BoxLayout(orientation='vertical',padding=dp(12),spacing=dp(8)); box.add_widget(Label(text=msg, color=(1,1,1,1), markup=True)); pop=Popup(title=title,content=box,size_hint=(.88,.45)); box.add_widget(UI.btn('OK',pop.dismiss,(0.0,0.45,0.25,1),48)); pop.open()
    def home(self):
        self.clear(); stats=self.stats()
        self.rootbox.add_widget(UI.label('Painel Operacional',24,True,dp(46)))
        cards=GridLayout(cols=2,spacing=dp(8),size_hint_y=None); cards.bind(minimum_height=cards.setter('height'))
        for t in [f'ESTOQUE\n{stats[0]} produtos', f'ALERTAS\n{stats[1]} baixo', f'ENTRADAS\n{stats[2]} registros', f'SAÍDAS\n{stats[3]} registros']:
            cards.add_widget(UI.btn(t,lambda:None,(0.01,0.12,0.25,1),86))
        self.rootbox.add_widget(cards)
        grid=GridLayout(cols=2,spacing=dp(8),size_hint_y=None); grid.bind(minimum_height=grid.setter('height'))
        for txt,fn,col in [('📦 Produtos',self.produtos,(0,0.32,0.65,1)),('➕ Entrada',self.entrada,(0,0.32,0.65,1)),('➖ Saída',self.saida,(0.75,0.38,0,1)),('✅ Conferência',self.conferencia,(0,0.32,0.65,1)),('⚠️ Alertas',self.alertas,(0.75,0.38,0,1)),('📊 Relatórios',self.relatorios,(0,0.32,0.65,1)),('💾 Backup',self.backup,(0.0,0.45,0.25,1)),('❔ Ajuda',self.ajuda,(0.2,0.2,0.3,1))]: grid.add_widget(UI.btn(txt,fn,col,76))
        self.rootbox.add_widget(grid)
    def stats(self):
        p=executar('select count(*) n from produtos where ativo=1',one=True)['n']; a=executar('select count(*) n from produtos where ativo=1 and estoque<=minimo',one=True)['n']; e=executar("select count(*) n from movimentos where tipo='ENTRADA'",one=True)['n']; s=executar("select count(*) n from movimentos where tipo='SAIDA'",one=True)['n']; return p,a,e,s
    def voltar(self): self.rootbox.add_widget(UI.btn('🏠 Voltar ao início',self.home,(0.1,0.1,0.16,1),52))
    def produtos(self):
        self.clear(); self.rootbox.add_widget(UI.label('Produtos cadastrados',22,True)); self.rootbox.add_widget(UI.btn('➕ Cadastrar novo produto',self.form_prod,(0,0.45,0.25,1),58))
        sv=ScrollView(); gl=GridLayout(cols=1,spacing=dp(6),size_hint_y=None); gl.bind(minimum_height=gl.setter('height'))
        for r in executar('select * from produtos where ativo=1 order by nome'):
            gl.add_widget(UI.btn(f"{r['codigo']} | {r['nome']}\nSaldo: {fmt(r['estoque'])} {r['unidade']} | Mín: {fmt(r['minimo'])}",lambda x=r:self.editar_prod(x),(0.01,0.12,0.25,1),72))
        sv.add_widget(gl); self.rootbox.add_widget(sv); self.voltar()
    def form_prod(self,r=None):
        self.clear(); self.rootbox.add_widget(UI.label('Cadastro de produto',22,True)); codigo=UI.inp('Código',False); nome=UI.inp('Nome',False); cat=Spinner(text='NÃO PERECÍVEL',values=['CONGELADO','RESFRIADO','NÃO PERECÍVEL','HORTIFRUTI','LIMPEZA','DESCARTÁVEL'],size_hint_y=None,height=dp(48)); un=Spinner(text='KG',values=['KG','G','UN','PCT','CX','LT'],size_hint_y=None,height=dp(48)); est=UI.inp('Estoque atual',True); minimo=UI.inp('Estoque mínimo',True); loc=UI.inp('Localização'); obs=UI.inp('Observação')
        if r:
            codigo.text=r['codigo']; nome.text=r['nome']; cat.text=r['categoria']; un.text=r['unidade']; est.text=fmt(r['estoque']); minimo.text=fmt(r['minimo']); loc.text=r['localizacao'] or ''; obs.text=r['obs'] or ''
        for w in (codigo,nome,cat,un,est,minimo,loc,obs): self.rootbox.add_widget(w)
        def salvar():
            if not nome.text.strip(): return self.popup('Informe o nome do produto.')
            args=(codigo.text.strip().upper() or nome.text[:5].upper(),nome.text.strip().upper(),cat.text,un.text,float(est.text or 0),float(minimo.text or 0),loc.text.strip().upper(),obs.text.strip(),today())
            try:
                if r: executar('update produtos set codigo=?,nome=?,categoria=?,unidade=?,estoque=?,minimo=?,localizacao=?,obs=? where id=?',args[:-1]+(r['id'],))
                else: executar('insert into produtos(codigo,nome,categoria,unidade,estoque,minimo,localizacao,obs,criado_em) values(?,?,?,?,?,?,?,?,?)',args)
                self.popup('Produto salvo com sucesso.'); self.produtos()
            except Exception as e: self.popup(f'Erro ao salvar: {e}')
        self.rootbox.add_widget(UI.btn('💾 Salvar produto',salvar,(0,0.45,0.25,1))); self.voltar()
    def editar_prod(self,r): self.form_prod(r)
    def escolher_prod(self,callback,titulo):
        self.clear(); self.rootbox.add_widget(UI.label(titulo,22,True)); q=UI.inp('Digite parte do nome/código e toque em buscar'); self.rootbox.add_widget(q); area=ScrollView(); gl=GridLayout(cols=1,spacing=dp(6),size_hint_y=None); gl.bind(minimum_height=gl.setter('height')); area.add_widget(gl); self.rootbox.add_widget(area)
        def buscar():
            gl.clear_widgets(); termo='%'+q.text.strip().upper()+'%'; rows=executar('select * from produtos where ativo=1 and (upper(nome) like ? or upper(codigo) like ?) order by nome',(termo,termo))
            if not rows: gl.add_widget(UI.btn('Produto não encontrado. Toque aqui para cadastrar.',self.form_prod,(0.7,0.35,0,1),60))
            for r in rows: gl.add_widget(UI.btn(f"{r['nome']} | Saldo {fmt(r['estoque'])} {r['unidade']}",lambda x=r:callback(x),(0.01,0.12,0.25,1),62))
        self.rootbox.add_widget(UI.btn('🔎 Buscar produto',buscar,(0,0.32,0.65,1),56)); self.voltar()
    def entrada(self): self.escolher_prod(lambda r:self.mov_form(r,'ENTRADA'),'Entrada de estoque')
    def saida(self): self.escolher_prod(lambda r:self.mov_form(r,'SAIDA'),'Saída de estoque')
    def mov_form(self,r,tipo):
        self.clear(); self.rootbox.add_widget(UI.label(f'{tipo}: {r["nome"]}\nSaldo atual: {fmt(r["estoque"])} {r["unidade"]}',20,False,dp(70))); qtd=UI.inp('Quantidade',True); turno=Spinner(text='A - ALMOÇO',values=['A - ALMOÇO','B - JANTA','C - CEIA','NÃO SE APLICA'],size_hint_y=None,height=dp(48)); resp=UI.inp('Responsável'); obs=UI.inp('Observação')
        for w in (qtd,turno,resp,obs): self.rootbox.add_widget(w)
        def salvar():
            q=float(qtd.text or 0)
            if q<=0: return self.popup('Informe quantidade maior que zero.')
            novo=float(r['estoque'])+q if tipo=='ENTRADA' else float(r['estoque'])-q
            if tipo=='SAIDA' and novo<0: return self.popup('Bloqueado: saída maior que estoque disponível.')
            executar('insert into movimentos(produto_id,tipo,quantidade,data_mov,turno,resp,obs,criado_em) values(?,?,?,?,?,?,?,?)',(r['id'],tipo,q,today(),turno.text,resp.text,obs.text,today()))
            executar('update produtos set estoque=? where id=?',(novo,r['id']))
            self.popup(f'{tipo} registrada. Novo saldo: {fmt(novo)} {r["unidade"]}'); self.home()
        self.rootbox.add_widget(UI.btn('Confirmar',salvar,(0,0.45,0.25,1))); self.voltar()
    def conferencia(self): self.escolher_prod(lambda r:self.conf_form(r),'Conferência de estoque')
    def conf_form(self,r):
        self.clear(); self.rootbox.add_widget(UI.label(f'Conferência: {r["nome"]}\nSistema: {fmt(r["estoque"])} {r["unidade"]}',20,False,dp(70))); fis=UI.inp('Quantidade física encontrada',True); obs=UI.inp('Observação obrigatória'); self.rootbox.add_widget(fis); self.rootbox.add_widget(obs)
        def salvar():
            f=float(fis.text or 0); dif=f-float(r['estoque'])
            if not obs.text.strip(): return self.popup('Observação obrigatória.')
            executar('insert into conferencias(produto_id,sistema,fisico,diferenca,obs,criado_em) values(?,?,?,?,?,?)',(r['id'],r['estoque'],f,dif,obs.text,today()))
            executar('update produtos set estoque=? where id=?',(f,r['id']))
            self.popup(f'Conferência salva. Diferença: {fmt(dif)} {r["unidade"]}'); self.home()
        self.rootbox.add_widget(UI.btn('Ajustar e salvar conferência',salvar,(0,0.45,0.25,1))); self.voltar()
    def alertas(self):
        self.clear(); self.rootbox.add_widget(UI.label('Alertas de estoque baixo',22,True)); sv=ScrollView(); gl=GridLayout(cols=1,spacing=dp(6),size_hint_y=None); gl.bind(minimum_height=gl.setter('height'))
        rows=executar('select * from produtos where ativo=1 and estoque<=minimo order by nome')
        if not rows: gl.add_widget(UI.label('Nenhum alerta no momento.',18,False,60))
        for r in rows: gl.add_widget(UI.label(f'⚠️ {r["nome"]}: {fmt(r["estoque"])} {r["unidade"]} | mínimo {fmt(r["minimo"])}',17,False,54))
        sv.add_widget(gl); self.rootbox.add_widget(sv); self.voltar()
    def relatorios(self):
        self.clear(); self.rootbox.add_widget(UI.label('Relatórios',22,True)); self.rootbox.add_widget(UI.btn('Gerar CSV de estoque',self.csv_estoque,(0,0.32,0.65,1))); self.rootbox.add_widget(UI.btn('Gerar CSV de movimentos',self.csv_mov,(0,0.32,0.65,1))); self.voltar()
    def csv_estoque(self):
        arq=os.path.join(REL,'estoque_atual.csv'); rows=executar('select codigo,nome,categoria,unidade,estoque,minimo,localizacao,obs from produtos order by nome')
        with open(arq,'w',newline='',encoding='utf-8') as f:
            w=csv.writer(f,delimiter=';'); w.writerow(['CODIGO','NOME','CATEGORIA','UN','ESTOQUE','MINIMO','LOCAL','OBS']); [w.writerow([x[k] for k in x.keys()]) for x in rows]
        self.popup(f'Relatório criado em:\n{arq}')
    def csv_mov(self):
        arq=os.path.join(REL,'movimentos.csv'); rows=executar('select m.criado_em,p.nome,m.tipo,m.quantidade,m.turno,m.resp,m.obs from movimentos m join produtos p on p.id=m.produto_id order by m.id desc')
        with open(arq,'w',newline='',encoding='utf-8') as f:
            w=csv.writer(f,delimiter=';'); w.writerow(['DATA','PRODUTO','TIPO','QTD','TURNO','RESP','OBS']); [w.writerow([x[k] for k in x.keys()]) for x in rows]
        self.popup(f'Relatório criado em:\n{arq}')
    def backup(self):
        nome=os.path.join(BKP,'backup_express_'+datetime.datetime.now().strftime('%Y%m%d_%H%M%S')+'.zip')
        with zipfile.ZipFile(nome,'w',zipfile.ZIP_DEFLATED) as z:
            if os.path.exists(DB): z.write(DB,'data/estoque_express.db')
            for root,_,files in os.walk(REL):
                for f in files: z.write(os.path.join(root,f),os.path.relpath(os.path.join(root,f),BASE))
        self.popup(f'Backup criado:\n{nome}')
    def ajuda(self):
        self.clear(); self.rootbox.add_widget(UI.label('Ajuda rápida',22,True)); self.rootbox.add_widget(UI.label('1. Cadastre produtos.\n2. Lance entradas.\n3. Lance saídas por turno.\n4. Faça conferência com observação.\n5. Gere backup diário.\n\nRegra: entrou, lance. saiu, baixe. conferiu, registre.',16,False,220)); self.voltar()

if __name__=='__main__': ExpressApp().run()
