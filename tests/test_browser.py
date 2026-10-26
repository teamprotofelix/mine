from playwright.sync_api import sync_playwright
from pathlib import Path
import re,base64,json
base=Path(__file__).resolve().parent.parent
html=(base/'index.html').read_text()
css=(base/'style.css').read_text()
engine=(base/'engine.js').read_text()
game=(base/'game.js').read_text()
assets={f'assets/{f.name}':'data:image/webp;base64,'+base64.b64encode(f.read_bytes()).decode() for f in (base/'assets').glob('*.webp')}
for key,val in assets.items():
    html=html.replace('src="'+key+'"','src="'+val+'"')
    css=css.replace('url(\''+key+'\')','url(\''+val+'\')')
html=html.replace('<link rel="stylesheet" href="style.css">','<style>'+css+'</style>')
shim='<script>window.__art='+json.dumps(assets)+';(()=>{const d=Object.getOwnPropertyDescriptor(HTMLImageElement.prototype,"src");Object.defineProperty(HTMLImageElement.prototype,"src",{get(){return d.get.call(this)},set(s){d.set.call(this,window.__art[s]||s)}})})();</script>'
html=html.replace('<script src="engine.js"></script>',shim+'<script>'+engine+'</script>')
html=html.replace('<script src="game.js"></script>','<script>'+game+'</script>')
with sync_playwright() as p:
 browser=p.chromium.launch(headless=True,executable_path='/usr/bin/chromium',args=['--no-sandbox'])
 for viewport in ({'width':1440,'height':900},{'width':390,'height':844}):
  page=browser.new_page(viewport=viewport,device_scale_factor=1)
  errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
  page.set_content(html,wait_until='load');page.wait_for_timeout(400)
  before=page.evaluate('MineQuestDebug.status()');assert before['rows']==9 and before['cols']==9,before
  assert page.locator('.cell').count()==81
  page.locator('.cell').first.click();page.wait_for_timeout(160)
  after=page.evaluate('MineQuestDebug.status()');assert after['generated'] and after['openSafe']>=1 and after['hearts']==4,after
  assert not errors,errors
  print('PASS browser viewport',viewport,'opened',after['openSafe'],'errors',errors)
  page.screenshot(path=str(base/f'tests/screen_{viewport["width"]}.png'),full_page=True)
  # interaction: flag mode and new game
  page.click('#flagMode');assert page.locator('#flagMode').get_attribute('aria-pressed')=='true'
  page.click('#newGame');assert page.evaluate('MineQuestDebug.status().generated') is False
  page.close()
 page=browser.new_page()
 page.set_content(html)
 page.select_option('#modeSelect','classic');assert page.locator('.cell').count()==81
 page.locator('.cell').nth(4).click(button='right');assert page.evaluate('MineQuestDebug.status().flags')==1
 page.locator('.cell').nth(4).click(button='right');assert page.evaluate('MineQuestDebug.status().flags')==0
 page.locator('.cell').nth(0).click();assert page.evaluate('MineQuestDebug.status().openSafe')>0
 page.select_option('#difficultySelect','expert');assert page.locator('.cell').count()==480
 print('PASS classic, right-click toggle, expert 480 tiles')
 browser.close()
# Enhanced integration cases, using an instrumented copy of the controller solely in test runtime.
# Game files shipped to the user do NOT expose mine locations or controls.
code=html.replace('<script>'+game+'</script>','<script>'+game.replace('  init();\n  // Expose',"  window.__mqTest={get cells(){return game.cells},get game(){return game},reveal:revealAt,flag:flagAt,skill:skill,tick:tick};\n  init();\n  // Expose")+'</script>')
with sync_playwright() as p:
 b=p.chromium.launch(headless=True,executable_path='/usr/bin/chromium',args=['--no-sandbox'])
 page=b.new_page();errs=[];page.on('pageerror',lambda e:errs.append(str(e)))
 page.set_content(code)
 page.evaluate('''() => {let t=window.__mqTest;t.reveal(0);if(!t.game.generated)throw Error('No first click');const mine=t.cells.find(c=>c.mine&&!c.open);if(!mine)throw Error('No mine');t.flag(mine.index);let scored=t.game.score;t.flag(mine.index);t.flag(mine.index);if(t.game.score!==scored)throw Error('Repeated flag score exploit');t.skill('scan');}''')
 assert page.evaluate('window.__mqTest.game.energy')>=0
 page.evaluate('''() => {const t=window.__mqTest;for(let i=0;i<t.cells.length;i++)if(!t.cells[i].mine&&!t.cells[i].open)t.reveal(i);}''')
 result={'state':page.evaluate('MineQuestDebug.status()'),'unlocked':page.locator('.stage-card').nth(1).is_enabled()}
 assert result['state']['ended'] and result['state']['bossHp']==0 and result['unlocked'], result
 assert page.locator('#modal').is_visible()
 page.click('#modalPrimary')
 assert page.evaluate('MineQuestDebug.status().stage')==1
 page.select_option('#modeSelect','classic')
 page.evaluate('''() => {const t=window.__mqTest;t.reveal(0);const mine=t.cells.find(c=>c.mine);t.reveal(mine.index);}''')
 assert page.evaluate('MineQuestDebug.status().ended')
 assert '쓰러졌습니다' in page.locator('#modalTitle').inner_text()
 assert not errs,errs
 print('PASS win/unlock/next-stage, repeated-flag score protection, scan skill, classic loss, modal transitions')
 b.close()
with sync_playwright() as p:
 b=p.chromium.launch(headless=True,executable_path='/usr/bin/chromium',args=['--no-sandbox'])
 page=b.new_page();issues=[];page.on('pageerror',lambda e:issues.append(str(e)))
 page.set_content(code)
 page.locator('.cell').first.click()
 # Force a boss telegraph and resolve it by clicking the displayed safe tile.
 page.evaluate('window.__mqTest.game.nextAttackAt=performance.now()-1000')
 page.wait_for_timeout(70)
 first_target=page.evaluate('window.__mqTest.game.attackTarget')
 assert first_target>=0,first_target
 assert page.locator('.cell.threatened').count()==1
 page.evaluate('(i)=>window.__mqTest.reveal(i)',first_target)
 assert page.evaluate('window.__mqTest.game.attackTarget')==-1
 # After recovering cooldown, next attack is absorbed by a skill-generated shield.
 page.evaluate('''() => {const t=window.__mqTest;t.game.energy=12;t.skill('shield');t.game.nextAttackAt=performance.now()-1;}''')
 page.wait_for_timeout(70)
 assert page.evaluate('window.__mqTest.game.attackTarget')>=0
 before=page.evaluate('window.__mqTest.game.hearts')
 page.evaluate('window.__mqTest.game.attackDeadline=performance.now()-1')
 page.wait_for_timeout(75)
 assert page.evaluate('window.__mqTest.game.hearts')==before
 assert page.evaluate('window.__mqTest.game.shield')==0
 page.click('#pauseButton');assert page.locator('body').evaluate('(b)=>b.classList.contains("paused")')
 page.click('#pauseButton');assert not page.locator('body').evaluate('(b)=>b.classList.contains("paused")')
 assert not issues,issues
 print('PASS boss telegraph, defuse, shield absorption, pause/resume')
 b.close()
