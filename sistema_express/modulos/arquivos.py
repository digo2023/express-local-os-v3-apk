from pathlib import Path
import os
import shutil
from configuracao import (
    PASTA_ANALITICOS, PASTA_ORDENS_COMPRA, PASTA_BACKUPS_IMPORTAR,
    PASTA_OUTROS_IMPORTAR, IMPORT_DIR
)
from modulos.interface import header, ask, warn, tabela, info, ok

PASTAS = {
    'analitico': PASTA_ANALITICOS,
    'oc': PASTA_ORDENS_COMPRA,
    'backup': PASTA_BACKUPS_IMPORTAR,
    'outros': PASTA_OUTROS_IMPORTAR,
}
EXTENSOES = {
    'analitico': ['.pdf'],
    'oc': ['.pdf', '.csv'],
    'backup': ['.zip'],
    'outros': ['.pdf', '.csv', '.xlsx', '.xls', '.zip', '.xml'],
}

def _apk():
    return os.environ.get('SISTEMA_EXPRESS_APK') == '1'

def _exts(exts):
    return {e.lower() if str(e).startswith('.') else f'.{str(e).lower()}' for e in exts}

def _pastas_publicas():
    bases = [
        Path('/storage/emulated/0/Download'),
        Path('/storage/emulated/0/Downloads'),
        Path('/storage/emulated/0/Documents'),
        Path('/storage/emulated/0'),
        Path('/sdcard/Download'),
        Path('/sdcard/Documents'),
        Path('/sdcard'),
    ]
    return [p for p in bases if p.exists() and p.is_dir()]

def _listar(pasta, exts):
    pasta.mkdir(parents=True, exist_ok=True)
    permitidas = _exts(exts)
    locais = [pasta]
    if _apk():
        locais.extend(_pastas_publicas())

    achados = []
    vistos = set()
    for base in locais:
        try:
            if str(base) in ('/storage/emulated/0', '/sdcard'):
                candidatos = list(base.glob('*'))
            else:
                candidatos = list(base.rglob('*'))
            for arq in candidatos:
                try:
                    if arq.is_file() and arq.suffix.lower() in permitidas:
                        chave = str(arq.resolve()) if arq.exists() else str(arq)
                        if chave not in vistos:
                            vistos.add(chave)
                            achados.append(arq)
                except Exception:
                    continue
        except Exception:
            continue
    return sorted(achados, key=lambda a: (str(a.parent).lower(), a.name.lower()))

def _resolver(caminho, exts):
    texto = str(caminho or '').strip().strip('"').strip("'")
    if not texto:
        return None
    p = Path(texto).expanduser()
    if p.exists() and p.is_file():
        return p

    nomes = [texto, Path(texto).name]
    if not any(texto.lower().endswith(e) for e in _exts(exts)):
        for e in _exts(exts):
            nomes.append(texto + e)
            nomes.append(Path(texto).name + e)

    bases = [Path.cwd(), IMPORT_DIR]
    bases.extend(_pastas_publicas())
    for base in bases:
        for nome in nomes:
            cand = base / nome
            if cand.exists() and cand.is_file():
                return cand
        try:
            alvo = Path(texto).name.lower()
            for cand in base.rglob('*'):
                if cand.is_file() and cand.name.lower() == alvo:
                    return cand
        except Exception:
            pass
    return None

def _copiar(origem, destino_pasta):
    origem = Path(origem)
    destino_pasta.mkdir(parents=True, exist_ok=True)
    destino = destino_pasta / origem.name
    if destino.exists():
        base, ext = destino.stem, destino.suffix
        i = 2
        while destino.exists():
            destino = destino_pasta / f'{base}_{i}{ext}'
            i += 1
    try:
        shutil.copy2(origem, destino)
        return destino
    except Exception:
        return origem

def selecionar_arquivo(tipo='outros', titulo='SELECIONAR ARQUIVO'):
    pasta = PASTAS.get(tipo, PASTA_OUTROS_IMPORTAR)
    exts = EXTENSOES.get(tipo, EXTENSOES['outros'])
    while True:
        header(titulo)
        info(f'Pasta interna: {pasta}')
        if _apk():
            info('No Android, deixe o arquivo em Download. Você pode escolher da lista ou digitar só o nome.')
        arquivos = _listar(pasta, exts)
        if arquivos:
            tabela('ARQUIVOS ENCONTRADOS', ['Nº', 'Arquivo', 'Pasta', 'Tamanho'], [
                (i + 1, a.name, str(a.parent)[-34:], f'{a.stat().st_size/1024:.1f} KB')
                for i, a in enumerate(arquivos)
            ], 1000000)
        else:
            warn('Nenhum arquivo encontrado em Download/Documents ou na pasta interna.')

        print('\n1 - Escolher arquivo listado')
        print('2 - Digitar caminho ou nome do arquivo')
        print('999 - Voltar')
        op = ask('Escolha', required=True)

        if op == '999':
            return ''
        if op == '1':
            if not arquivos:
                warn('Copie o arquivo para Download e tente novamente.')
                continue
            num = ask('Número do arquivo', required=True)
            if num.isdigit() and 1 <= int(num) <= len(arquivos):
                escolhido = arquivos[int(num) - 1]
                final = _copiar(escolhido, pasta)
                if final != escolhido:
                    ok(f'Arquivo importado para: {final}')
                return str(final)
            warn('Número inválido.')
        elif op == '2':
            caminho = ask('Caminho completo ou nome do arquivo', required=True)
            p = _resolver(caminho, exts)
            if p and p.exists() and p.is_file():
                final = _copiar(p, pasta)
                if final != p:
                    ok(f'Arquivo importado para: {final}')
                return str(final)
            warn('Arquivo não encontrado. Coloque em Download ou confira o nome.')
        else:
            warn('Opção inválida.')
