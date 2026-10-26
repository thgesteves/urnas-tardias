# /// script
# requires-python = ">=3.10"
# ///
"""Estima para quem foram os votos depois das 17h nas urnas estendidas e quem venceu em cada UF.

O log da urna diz a hora de cada voto, mas não o candidato (o voto é secreto). Por isso, em cada seção
os votos tardios são divididos na proporção do Boletim de Urna (BU) daquela seção.
Lê secoes.csv (gerado por analisa.py), baixa BU e resultado por UF do TSE e grava candidatos_uf.csv."""
import csv, json, os, sys, time, threading, random, urllib.request, urllib.error, concurrent.futures as cf, collections

DIR = os.path.dirname(os.path.abspath(__file__))
SITE = "https://resultados.tse.jus.br/oficial/ele2026"
URNA = f"{SITE}/arquivo-urna/3221/dados"
ELEICAO = "6258"  # 2º turno, cargo 1 (Presidente)
LULA, FLAVIO = "13", "22"
RPS = float(os.environ.get("RPS", "10"))
lock, prox = threading.Lock(), [time.monotonic()]


def get(url):
    for i in range(8):
        with lock:
            agora = time.monotonic()
            prox[0] = max(prox[0], agora) + 1 / RPS
            d = prox[0] - agora - 1 / RPS
        if d > 0:
            time.sleep(d)
        try:
            return urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"}), timeout=60).read()
        except urllib.error.HTTPError as e:
            if e.code == 404:
                raise
        except Exception:
            pass
        time.sleep(min(60, 2 ** i) + random.random())
    raise RuntimeError(f"falhou: {url}")


def der(b):
    """Decodifica DER em [(tag, filhos | bytes)]."""
    out, i = [], 0
    while i < len(b):
        t, n = b[i], b[i + 1]
        i += 2
        if n & 0x80:
            k = n & 0x7F
            n, i = int.from_bytes(b[i:i + k], "big"), i + k
        v, i = b[i:i + n], i + n
        out.append((t, der(v) if t & 0x20 else v))
    return out


def presidente(raw):
    """Votos do cargo Presidente no BU: {'13': n, '22': n, 'branco': n, 'nulo': n}.
    O BU vem num envelope ASN.1; o conteúdo é o OCTET STRING do envelope. Cada TotalVotosCargo é
    SEQUENCE { [1] cargo, ordem, SEQUENCE OF { [1] tipo, [2] quantidade, [3] { partido, número } } }."""
    num = lambda b: int.from_bytes(b, "big")
    res = collections.Counter()

    def busca(nos):
        for _, v in nos:
            if not isinstance(v, list):
                continue
            if v and v[0][0] == 0x81 and len(v) >= 3 and isinstance(v[2][1], list) and all(isinstance(x[1], list) for x in v[2][1]):
                if num(v[0][1]) == 1:
                    for _, vv in v[2][1]:
                        d = dict(vv)
                        tipo = num(d[0x81])
                        k = str(num(d[0xA3][1][1])) if tipo == 1 else {2: "branco", 3: "nulo"}.get(tipo, f"tipo{tipo}")
                        res[k] += num(d[0x82])
                continue
            busca(v)

    busca(der([v for t, v in der(raw)[0][1] if t == 0x04][0]))
    return dict(res)


def bu(x):
    uf, mu, zo, se = x["uf"].lower(), x["cd_mun"], x["zona"], x["secao"]
    d = f"{URNA}/{uf}/{mu}/{zo}/{se}"
    out = {k: x[k] for k in ("uf", "cd_mun", "zona", "secao")}
    try:
        h = json.loads(get(f"{d}/p003221-{uf}-m{mu}-z{zo}-s{se}-aux.json"))["hashes"][-1]
        nm = [a["nm"] for a in h["arq"] if a.get("tp") == "bu"]
        if not nm:
            return {**out, "erro": "sem bu"}
        return {**out, "pres": presidente(get(f"{d}/{h['hash']}/{nm[0]}"))}
    except Exception as e:
        return {**out, "erro": repr(e)}


def resultado_uf(uf):
    """Votos de Lula e Flávio na UF, do arquivo de resultado do TSE."""
    path = f"{DIR}/dados/resultado/{uf}.json"
    if not os.path.exists(path):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        open(path, "wb").write(get(f"{SITE}/{ELEICAO}/dados/{uf}/{uf}-c0001-e00{ELEICAO}-u.json"))
    votos = {}

    def busca(o):
        if isinstance(o, dict):
            if "vap" in o and "n" in o and "sqcand" in o:
                votos[o["n"]] = int(o["vap"])
            for v in o.values():
                busca(v)
        elif isinstance(o, list):
            for v in o:
                busca(v)

    busca(json.load(open(path, encoding="utf-8-sig")))
    return votos


def main():
    secoes = [x for x in csv.DictReader(open(f"{DIR}/secoes.csv"))
              if x["uf"] != "ZZ" and x["classe"] == "estendida" and int(x["votos_apos_17h"]) > 0]
    chave = lambda r: (r["uf"], r["cd_mun"], r["zona"], r["secao"])
    path, bus = f"{DIR}/dados/bu.jsonl", {}
    os.makedirs(f"{DIR}/dados", exist_ok=True)
    if os.path.exists(path):
        for l in open(path):
            r = json.loads(l)
            if "pres" in r:
                bus[chave(r)] = r["pres"]
    falta = [x for x in secoes if chave(x) not in bus]
    print(f"{len(secoes)} seções estendidas com voto depois das 17h, {len(falta)} BUs a baixar", file=sys.stderr)
    with open(path, "a") as f, cf.ThreadPoolExecutor(16) as ex:
        for i, r in enumerate(ex.map(bu, falta), 1):
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
            if "pres" in r:
                bus[chave(r)] = r["pres"]
            if i % 500 == 0:
                print(f"  {i}/{len(falta)}", file=sys.stderr)

    est = collections.Counter(x["uf"] for x in csv.DictReader(open(f"{DIR}/secoes.csv")) if x["classe"] == "estendida")
    urnas = collections.Counter(x["uf"] for x in csv.DictReader(open(f"{DIR}/secoes.csv")))
    agg, sem_bu = collections.defaultdict(collections.Counter), 0
    for x in secoes:
        p = bus.get(chave(x))
        if not p:
            sem_bu += 1
            continue
        v, n = int(x["votos_apos_17h"]), sum(p.values())
        a = agg[x["uf"]]
        a["tardios"] += v
        a["lula"] += v * p.get(LULA, 0) / n
        a["flavio"] += v * p.get(FLAVIO, 0) / n
        a["branco_nulo"] += v * (p.get("branco", 0) + p.get("nulo", 0)) / n
    if sem_bu:
        print(f"aviso: {sem_bu} seções sem BU ficaram de fora", file=sys.stderr)

    linhas = []
    for uf, a in sorted(agg.items(), key=lambda kv: -kv[1]["tardios"]):
        r = resultado_uf(uf.lower())
        lu, fl = r[LULA], r[FLAVIO]
        linhas.append({"uf": uf, "urnas": urnas[uf], "urnas_estendidas": est[uf], "votos_apos_17h": a["tardios"],
                       "est_lula": round(a["lula"]), "est_flavio": round(a["flavio"]), "est_branco_nulo": round(a["branco_nulo"]),
                       "uf_votos_lula": lu, "uf_votos_flavio": fl, "uf_pct_lula": round(100 * lu / (lu + fl), 2),
                       "vencedor_uf": "Lula" if lu > fl else "Flávio"})
    with open(f"{DIR}/candidatos_uf.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(linhas[0]))
        w.writeheader(); w.writerows(linhas)

    print(f"{'UF':4}{'estendidas':>11}{'tardios':>9}{'Lula':>7}{'Flávio':>8}{'br/nulo':>8}   vencedor na UF")
    for x in linhas:
        pv = x["uf_pct_lula"] if x["vencedor_uf"] == "Lula" else 100 - x["uf_pct_lula"]
        print(f"{x['uf']:4}{x['urnas_estendidas']:11}{x['votos_apos_17h']:9}{x['est_lula']:7}{x['est_flavio']:8}{x['est_branco_nulo']:8}   {x['vencedor_uf']} {pv:.1f}%")
    t = {k: sum(x[k] for x in linhas) for k in ("votos_apos_17h", "est_lula", "est_flavio", "est_branco_nulo")}
    print(f"{'BR':4}{'':11}{t['votos_apos_17h']:9}{t['est_lula']:7}{t['est_flavio']:8}{t['est_branco_nulo']:8}")


if __name__ == "__main__":
    main()
