import importlib.util,sys,json,collections,os
from pathlib import Path
from playwright.sync_api import sync_playwright
def load(p):
    s=importlib.util.spec_from_file_location("p"+str(abs(hash(p))),p); m=importlib.util.module_from_spec(s); s.loader.exec_module(m); return m
def page_for(mod,out):
    pay=mod.collect(Path('jobs'),None,''); pay['count']=20
    Path(out).write_text(mod.build_html(pay),encoding='utf-8'); return pay
res={}
with sync_playwright() as p:
    b=p.chromium.launch()
    for name,path,runs in [("before","old/practice.py",20),("after","new_practice.py",200)]:
        page_for(load(path),f"{name}.html")
        pos=collections.Counter(); perrun=[]; scores=[]; graded_ok=True
        for r in range(runs):
            pg=b.new_page(); pg.goto('file://'+os.path.abspath(f'{name}.html')); pg.wait_for_timeout(100)
            pg.click('#start')
            c=collections.Counter(); score=0
            for i in range(20):
                # which displayed button is correct? read text of the right answer from the original data via state
                ans=pg.evaluate("(()=>{const q=state.qs[state.i];return q.answer})()")
                L='ABCD'[ans]; c[L]+=1; pos[L]+=1
                pg.click(f'.opt[data-j="{ans}"]')
                ok=pg.evaluate("document.querySelector('.feedback').classList.contains('bad')")
                if ok: graded_ok=False
                pg.click('#next')
            txt=pg.inner_text('.score'); scores.append(txt); perrun.append(max(c.values()))
            pg.close()
        res[name]={"runs":runs,"positions":dict(sorted(pos.items())),"max_same_letter_per_quiz":{"mean":round(sum(perrun)/len(perrun),1),"max":max(perrun)},"scores":collections.Counter(scores).most_common(2),"graded_ok":graded_ok}
    b.close()
print(json.dumps(res,indent=1))
json.dump(res,open('retest_results.json','w'),indent=1)
