'use strict';
const $=id=>document.getElementById(id), db=window.RAMA_DB||{sections:[],categories:[],videos:[],items:[]};
const safe=v=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const norm=v=>String(v??'').toLowerCase().replace(/ё/g,'е').normalize('NFKC');
const tokens=q=>norm(q).match(/"[^"]+"|[\p{L}\p{N}]+/gu)?.map(s=>s.replace(/"/g,''))||[];
const catMap=new Map(db.categories.map(c=>[c.id,c])), vidMap=new Map(db.videos.map(v=>[v.id,v]));
const chapters=new Map();for(const item of db.items){if(!chapters.has(item.video))chapters.set(item.video,[]);chapters.get(item.video).push(item)}
const catNames=ids=>ids.map(c=>catMap.get(c)?.name||'').join(' ');
const byId=new Map();
const typeName={fragment:'Фрагмент',video:'Полное видео',overview:'Обзор',service:'Служебный фрагмент'};
const videoText=new Map(db.videos.map(v=>[v.id,norm([v.title,...(v.descriptions||[]),...(v.references||[]).map(r=>r.text),v.date].join(' '))]));
const index=db.items.map(i=>{const v=vidMap.get(i.video)||{};return {...i,v,titleIndex:norm(i.title),topicIndex:norm(i.title+' '+catNames(i.cats||[])+' '+(i.keywords||[]).join(' ')),videoIndex:videoText.get(i.video)||''}});
const videoIndex = [...vidMap.values()].map(v => {
  const items = chapters.get(v.id) || [];
  const cats = [...new Set(items.flatMap(i=>i.cats || []))];
  const topics = items.map(i=>[i.title,...(i.keywords || [])].join(' '));
  return {
    id:'video:'+v.id, video:v.id, v, title:v.title, type:'video', cats,
    titleIndex:norm(v.title), topicIndex:norm([v.title,catNames(cats),...topics].join(' ')),
    videoIndex:videoText.get(v.id)
  };
});
for(const i of [...index,...videoIndex])byId.set(i.id,i);
// Имена из публичных меток каталога. Связи вычисляются по точному совпадению.
const personNames = [
  "Адикарта дас",
  "Ананда Говинда прабху",
  "Ананда Манджари д.д.",
  "Ананта Гаура дас",
  "Арча Виграха прабху",
  "Аударья Дхама дас (Олег Торсунов)",
  "Ахилананда прабху",
  "Ачьюта Прия прабху",
  "Бриджабаси прабху",
  "Бхавананда дас",
  "Бхакти Бхринги Говинда Свами",
  "Бхакти Вигьяна Госвами",
  "Бхакти Викаша Свами",
  "Бхакти Вишрамбхи Мадхава Свами",
  "Бхакти Расаяна Сагара Свами",
  "Бхану Свами",
  "Бхима-Карма прабху",
  "Вайшешика прабху",
  "Ведагарбха дас",
  "Владимир Древс",
  "Гауранга прабху",
  "Гоур Говинда Свами",
  "Дамодара прабху",
  "Девамрита Свами",
  "Джанаки Деви Даси",
  "Джаядвайта Свами",
  "Дина Бандху прабху",
  "Дмитрий Кузьмин",
  "Дханурдхара Свами",
  "Дхирашанта Дас Госвами",
  "Индрадьюмна Свами",
  "Индранила Кришна прабху",
  "Каунтея дас",
  "Кешава Бхарати Дас Госвами",
  "Кешава Кришна прабху",
  "Кришна Дваяпаяна прабху",
  "Мадхавананда прабху",
  "Манибандха дас",
  "Маха Баларам дас",
  "Махаджана дас",
  "Махимарнава дас",
  "Нарада прабху",
  "Ниранджана Свами",
  "Патита Павана дас (Вячеслав Рузов)",
  "Прахладананда Свами",
  "Пуньяда прабху",
  "Радха Вриндавана Чандра Свами (Габинатха дас)",
  "Радха Манохара прабху",
  "Радханатха Свами",
  "Садананда Свами",
  "Садху Сева прабху",
  "Санкиртана прабху",
  "Тарас прабху",
  "Тарун Кришна дас",
  "Тривикрама дас",
  "Харибхакти дас",
  "Харикеша Свами",
  "Хридаянанда Госвами",
  "Чайтанья Чандра Чаран дас (Александр Хакимов)",
  "Чайтанья Чандра дас (англоязычный автор)",
  "Чайтанья Чандрадоя прабху",
  "Чинмой Кришна Дас",
  "Шиварама Свами",
  "Шикшаштака прабху",
  "Шрила Прабхупада",
  "Шубхананда дас",
  "Шудхадвайти Свами",
  "Шьямасундара прабху"
];
const people = new Map(personNames.map(name => [name, {items:new Set(), videos:new Set()}]));
for (const item of db.items) {
  for (const keyword of item.keywords || []) {
    const entry = people.get(keyword);
    if (entry) {
      entry.items.add(item.id);
      entry.videos.add(item.video);
    }
  }
}
$('peopleList').innerHTML = [...people.entries()]
  .filter(([, entry]) => entry.items.size)
  .sort(([a], [b]) => a.localeCompare(b, 'ru'))
  .map(([name, entry]) => `<li><a href="#${new URLSearchParams({person:name})}"><span>${safe(name)}</span><small aria-label="Материалов: ${entry.items.size}">${entry.items.size}</small></a></li>`)
  .join('');
const expandedVideos = new Set();
function videoResults() {
  return !savedOnly && (mode === 'videos' || $('kind').value === 'video');
}
function layoutTab() { return videoResults() ? 'videos' : mode }
$('peopleTotal').textContent=$('peopleList').childElementCount;
let directoryOpen=false, person='', source='';
let bookmarks=new Set();try{bookmarks=new Set(JSON.parse(localStorage.getItem('rama-favorites')||'[]'));if(localStorage.getItem('rama-theme')==='light')document.body.classList.add('light')}catch(e){}
const archive=createShellingPanel(db.items,vidMap,()=>{limit=24;render(true)});
function archiveActive(){return category==='shelling' && mode==='items' && !savedOnly && !directoryOpen}
let category='',section='',mode='items',savedOnly=false,limit=24,last=[],searchTimer; const openedSections=new Set(['war']);function readLocation(){
const params=new URLSearchParams(location.hash.slice(1));
expandedVideos.clear();
directoryOpen=params.get('directory')==='people';
source=vidMap.has(params.get('source'))?params.get('source'):'';
person=people.has(params.get('person'))?params.get('person'):'';
savedOnly=params.get('saved')==='1';
mode='items';limit=24;$('kind').value='all';$('sort').value='relevance';
$('search').value=params.get('q')||'';category=catMap.has(params.get('cat'))?params.get('cat'):'';if(params.get('mode')==='videos')mode='videos';section=db.sections.some(s=>s.id===params.get('section'))?params.get('section'):'';if(category)section='';if(['all','fragment','video'].includes(params.get('kind'))) $('kind').value=params.get('kind');if(['relevance','new','old'].includes(params.get('sort'))) $('sort').value=params.get('sort');$('scope').value=params.get('scope')==='context'?'context':'topic';
archive.activate(archiveActive());archive.read(params);
}
readLocation();
function focusPersonView(){
  if ($('topicDrawer').open) closeTopics();
  if(directoryOpen)$('peopleTitle').focus();
  else if(person || source){jumpResults();$('heading').focus({preventScroll:true})}
}
window.addEventListener('hashchange',()=>{readLocation();categories();render();focusPersonView()});
function yt(id,t){return 'https://www.youtube.com/watch?v='+encodeURIComponent(id)+(t!=null?'&t='+Number(t)+'s':'')}
function timestamp(t){if(t==null)return '';const n=Number(t);return [Math.floor(n/3600),Math.floor(n%3600/60),n%60].map(x=>String(x).padStart(2,'0')).join(':')}
function linkURL(s){try{const u=new URL(s);return ['https:','http:'].includes(u.protocol)?u.href:''}catch{return ''}}
let highlightQuery, highlightPattern;
function hl(value) {
  const text = String(value ?? '');
  const query = $('search').value;
  if (highlightQuery !== query) {
    highlightQuery = query;
    const ts = tokens(query).sort((a,b) => b.length - a.length);
    highlightPattern = ts.length ? new RegExp(ts.map(t=>t.replace(/[.*+?^${}()|[\]\\]/g,'\\$&').replace(/е/g,'[её]')).join('|'),'giu') : null;
  }
  if (!highlightPattern) return safe(text);
  let html = '', offset = 0;
  for (const match of text.matchAll(highlightPattern)) {
    html += safe(text.slice(offset,match.index)) + '<mark>' + safe(match[0]) + '</mark>';
    offset = match.index + match[0].length;
  }
  return html + safe(text.slice(offset));
}
function score(i,ts){let s=0;const contextual=mode==='videos'||$('scope').value==='context';for(const t of ts){if(i.titleIndex.includes(t))s+=12;else if(i.topicIndex.includes(t))s+=6;else if(contextual&&i.videoIndex.includes(t))s+=1;else return -1}return s}
function countCats(){const m=new Map();for(const i of index)for(const c of i.cats||[])m.set(c,(m.get(c)||0)+1);return m}const counts=countCats();
function inSection(i,id){return i.cats?.some(c=>catMap.get(c)?.section===id)}
const sectionCounts=new Map(db.sections.map(s=>[s.id,index.filter(i=>inSection(i,s.id)).length]));
const videoCounts=new Map(db.categories.map(c=>[c.id,videoIndex.filter(i=>i.cats.includes(c.id)).length]));
const videoSectionCounts=new Map(db.sections.map(s=>[s.id,videoIndex.filter(i=>inSection(i,s.id)).length]));
function categories(){for(const d of $('categories').querySelectorAll('details')){if(d.open)openedSections.add(d.dataset.section);else openedSections.delete(d.dataset.section)}const active=db.categories.filter(c=>c.active!==false&&counts.get(c.id));const cc=videoResults()?videoCounts:counts,sc=videoResults()?videoSectionCounts:sectionCounts;$('categories').innerHTML=db.sections.map(s=>{const cs=active.filter(c=>c.section===s.id);return cs.length?`<details data-section="${safe(s.id)}" ${openedSections.has(s.id)||section===s.id||cs.some(c=>c.id===category)?'open':''}><summary>${safe(s.name)} <small>${sc.get(s.id)}</small></summary><button class="cat sectionlink ${section===s.id?'active':''}" data-section-select="${safe(s.id)}"><span>Все материалы раздела</span><small>${sc.get(s.id)}</small></button>${cs.map(c=>`<button class="cat ${c.parent?'child':''} ${category===c.id?'active':''}" data-cat="${safe(c.id)}"><span>${safe(c.name)}</span><small>${cc.get(c.id)}</small></button>`).join('')}</details>`:''}).join('');}
function clearFilters(){archive.activate(false);directoryOpen=false;person='';source='';clearTimeout(searchTimer);$('search').value='';$('kind').value='all';$('scope').value='topic';savedOnly=false;limit=24}
function jumpResults(){if($('topicDrawer').open)closeTopics(); $('heading').scrollIntoView({block:'start',behavior:'instant'})}
function clearForTopic(){
  const kind=$('kind').value;
  clearFilters(); $('kind').value=kind;
}
function setCategory(c){clearForTopic();category=c;section='';categories();render(true);jumpResults()}
function setSection(s){clearForTopic();category='';section=s;categories();render(true);jumpResults()}
function stats(){const entries=[['Видео',vidMap.size],['Тайм-коды',db.items.filter(i=>i.seconds!=null).length],['Тематические категории',db.categories.filter(c=>counts.get(c.id)).length],['Материалы каталога',db.items.filter(i=>i.type!=='service').length]];$('stats').innerHTML=entries.map(([k,v])=>`<div class="stat"><strong>${v.toLocaleString('ru-RU')}</strong><span>${k}</span></div>`).join('');if(db.preview||!db.items.length){$('notice').hidden=false;$('notice').innerHTML='<strong>Предварительная версия.</strong> '+(db.items.length?'Загружен только небольшой проверяемый образец из таблицы. ':'База ещё не импортирована. ')+'Полная база появится после сборки с исходным Excel.'}}
const layouts = ['list', 'grid', 'text'];
function preference(key, fallback) {
  try { return localStorage.getItem(key) ?? fallback } catch { return fallback }
}
function remember(key, value) {
  try { localStorage.setItem(key, value) } catch {}
}
function layoutPreference(tab, fallback) {
  const stored = preference('rama-layout-' + tab, fallback);
  return layouts.includes(stored) ? stored : fallback;
}
const views = {items: layoutPreference('items', 'list'), videos: layoutPreference('videos', matchMedia('(max-width:580px), (max-height:500px) and (pointer:coarse)').matches ? 'list' : 'grid')};
let groupEnabled = preference('rama-group', '0') === '1';
let groupedResults;
const closedGroups = new Set();
const plural = new Intl.PluralRules('ru');
function quantity(n, one, few, many) {
  const word = {one, few, many}[plural.select(n)] || many;
  return n.toLocaleString('ru-RU') + ' ' + word;
}
function thumbnail(video) {
  return `<span class="preview" aria-hidden="true"><img width="160" height="90" loading="lazy" alt="" src="https://i.ytimg.com/vi/${encodeURIComponent(video)}/mqdefault.jpg" onerror="this.hidden=true"></span>`;
}
function youtubeLink(video, seconds) {
  return `<a class="external" href="${safe(yt(video, seconds))}" target="_blank" rel="noopener noreferrer">YouTube ↗</a>`;
}
function keywordButton(item,k) {
  const city=archive.enabled && archive.city(k);
  return city && archive.meta(item.id)?.cities.includes(city)
    ? `<button data-event-place="${safe(city)}" aria-pressed="${archive.selected.has(city)}">${hl(k)}</button>`
    : `<button data-query="${safe(k)}" title="Поиск по метке">${hl(k)}</button>`;
}
function videoCard(item) {
  const id = safe(item.id), video = item.v;
  const count = (chapters.get(video.id) || []).filter(row => row.type !== 'service').length;
  const saved = bookmarks.has(item.id);
  return `<article class="result video-record">
    <h3><a href="video/${encodeURIComponent(video.id)}/">${hl(video.title)}</a></h3>
    ${views[layoutTab()] === 'text' ? '' : `<button class="thumb-link" data-open="${id}" aria-label="Смотреть полное видео">${thumbnail(video.id)}</button>`}
    <div class="meta">${safe(video.date)} ${count ? ` · <a href="#source=${encodeURIComponent(video.id)}">${quantity(count,'материал','материала','материалов')}</a>` : ''}</div>
    <div class="actions"><button class="primary" data-open="${id}">▷ Смотреть</button>
    ${youtubeLink(video.id)}
    <button class="bookmark ${saved?'on':''}" aria-pressed="${saved}" aria-label="${saved?'Удалить из избранного':'В избранное'}" data-bookmark="${id}">${saved?'★':'☆'}</button></div>
    <details class="record-info" data-record="${safe(video.id)}" ${expandedVideos.has(video.id)?'open':''}>
    <summary>О выпуске и тайм-коды</summary></details></article>`;
}
function recordContent(id) {
  const video = vidMap.get(id);
  const items = [...(chapters.get(id) || [])].sort((a,b)=>(a.seconds??Infinity)-(b.seconds??Infinity));
  const cats = new Set(items.flatMap(i=>i.cats || []));
  const words = new Set(items.flatMap(i=>i.keywords || []));
  const links = (video.references || []).filter(r=>linkURL(r.url));
  return `<div class="record-content">
    ${(video.descriptions||[]).map(d=>`<p>${hl(d)}</p>`).join('')}
    ${cats.size ? '<h4>Темы</h4><div class="tags">'+[...cats].map(c=>`<button data-cat="${safe(c)}">${safe(catMap.get(c)?.name)}</button>`).join('')+'</div>' : ''}
    ${words.size ? '<h4>Ключевые слова</h4><div class="tags">'+[...words].map(k=>`<button data-query="${safe(k)}">${hl(k)}</button>`).join('')+'</div>' : ''}
    ${items.length ? '<h4>Материалы выпуска</h4>'+items.map(i=>`<div class="chapter"><button data-open="${safe(i.id)}">${i.seconds==null?'Смотреть':timestamp(i.seconds)}</button><span>${hl(i.title)}</span></div>`).join('') : ''}
    ${links.length ? '<h4>Дополнительные источники</h4>'+links.map(r=>`<p><a target="_blank" rel="noopener noreferrer" href="${safe(linkURL(r.url))}">${safe(r.text||r.url)} ↗</a></p>`).join('') : ''}
  </div>`;
}
function card(i, nested=false) {
  const id = safe(i.id);
  const video = i.v;
  const tagged = bookmarks.has(i.id);
  const showImage = !nested && views[layoutTab()] !== 'text';
  const label = !category && catMap.get(i.cats?.[0])?.name;
  const tags = (i.keywords || []).map(k => keywordButton(i,k));
  if (label && !nested) tags.unshift(`<button data-cat="${safe(i.cats[0])}">${hl(label)}</button>`);
  const terms = tokens($('search').value);
  const context = $('scope').value === 'context' && terms.length
    ? video.descriptions?.find(text => terms.some(term => norm(text).includes(term)))
    : '';
  const description = i.description || context || ((i.type === 'video' || i.type === 'overview') && video.descriptions?.[0]);
  const source = !nested && video.title !== i.title ? hl(video.title) : '';
  const singleton = (archive.enabled ? archive.group==='video' : groupEnabled) && mode === 'items' && !nested;
  const info = !nested ? [source, archive.enabled && video.date ? 'Опубликовано: '+safe(video.date) : safe(video.date), singleton && '1 материал'].filter(Boolean).join(' · ') : '';
  const event = archive.enabled && archive.meta(i.id);
  return `<article class="result">
    <h3>${eventTitle(i)}</h3>
    ${event?.inferred ? `<div class="event-date">${safe(eventLabel(event.spec))} · предположительный год по публикации видео</div>` : ''}
    ${event?.evidence ? `<div class="event-date">События: ${safe(eventLabel(event.spec))} · <button class="external" data-open="${safe(event.evidence[1])}" title="${safe(event.evidence[2])}">Источник даты</button></div>` : ''}
    ${showImage ? `<button class="thumb-link" data-open="${id}" aria-label="Открыть видео">${thumbnail(i.video)}</button>` : ''}
    ${description ? `<p class="excerpt">${context ? 'Из описания видео · ' : ''}${hl(description)}</p>` : ''}
    ${tags.length ? `<div class="tags">${tags.join('')}</div>` : ''}
    ${info ? `<div class="meta">${info}</div>` : ''}
    <div class="actions">
      ${i.seconds != null ? `<button class="stamp" data-open="${id}" aria-label="Открыть с ${timestamp(i.seconds)}">${timestamp(i.seconds)}</button>` : `<span class="meta-type">${safe(typeName[i.type])}</span>`}
      <button class="primary" data-open="${id}">▷ Смотреть</button>
      ${youtubeLink(i.video, singleton ? null : i.seconds)}
      <button class="bookmark ${tagged ? 'on' : ''}" aria-pressed="${tagged}" data-bookmark="${id}" aria-label="${tagged ? 'Удалить из избранного' : 'В избранное'}">${tagged ? '★' : '☆'}</button>
    </div></article>`;
}
function groupResults() {
  const map = new Map();
  for (const item of last) {
    if (!map.has(item.video)) map.set(item.video, []);
    map.get(item.video).push(item);
  }
  const groups = [...map.values()];
  for (const items of groups) items.sort((a,b) => (a.seconds ?? Infinity) - (b.seconds ?? Infinity));
  return groups;
}
function eventTitle(item) {
  const quote=archive.enabled && archive.meta(item.id)?.quote;
  const pos=quote ? item.title.indexOf(quote) : -1;
  if(pos<0) return hl(item.title);
  return hl(item.title.slice(0,pos))+'<span class="event-date" title="Дата события">'+hl(quote)+'</span>'+hl(item.title.slice(pos+quote.length));
}
function archiveGroupCard(row) {
  return `<details class="video-group" data-video="${safe(row.key)}" ${closedGroups.has(row.key)?'':'open'}>
    <summary><span><strong>${safe(row.label)}</strong><small>${quantity(row.items.length,'материал','материала','материалов')}</small></span></summary>
    <div class="group-items">${row.items.map(i=>card(i)).join('')}</div></details>`;
}
function groupCard(items) {
  if (items.length === 1) return card(items[0]);
  const video = items[0].v;
  return `<details class="video-group" data-video="${safe(video.id)}" ${closedGroups.has(video.id) ? '' : 'open'}>
    <summary><span><strong>${hl(video.title)}</strong><small>${archive.enabled?'Опубликовано: ':''}${safe(video.date)} · ${quantity(items.length,'материал','материала','материалов')}</small></span>
    ${views[layoutTab()] === 'text' ? '' : thumbnail(video.id)}</summary>
    <div class="group-source">${youtubeLink(video.id)}</div>
    <div class="group-items">${items.map(i => card(i,true)).join('')}</div></details>`;
}
function paintResults(append=false) {
  const results = $('results');
  const grouping = videoResults() ? 'none' : archive.enabled ? archive.group : groupEnabled && mode==='items' ? 'video' : 'none';
  const grouped = grouping !== 'none';
  const eventGroups = grouped && grouping !== 'video';
  results.dataset.layout = views[layoutTab()];
  results.classList.toggle('grouped', grouped);
  for (const button of $('layouts').querySelectorAll('button')) {
    button.setAttribute('aria-pressed', String(button.dataset.layout === views[layoutTab()]));
  }
  $('groupOption').hidden = archive.enabled || videoResults();
  $('eventGrouping').hidden = !archive.enabled || videoResults();
  $('groupBy').checked = groupEnabled;
  if (grouped && !groupedResults) groupedResults = eventGroups ? archive.groupRows(last) : groupResults();
  const rows = grouped ? groupedResults : last;
  const visible = grouped ? Math.ceil(limit / 4) : limit;
  $('groupTools').hidden = videoResults() ? !rows.length : !grouped || !(eventGroups ? rows.length : rows.some(g => g.length > 1));
  $('count').textContent = grouping==='video'
    ? `Найдено: ${quantity(last.length,'материал','материала','материалов')} · ${rows.length} видео`
    : `Найдено: ${last.length.toLocaleString('ru-RU')}`;
  const start = append ? results.childElementCount : 0;
  const html = rows.slice(start,visible).map(row => eventGroups ? archiveGroupCard(row) : grouped ? groupCard(row) : row.id.startsWith('video:') ? videoCard(row) : card(row)).join('');
  if (append) results.insertAdjacentHTML('beforeend',html);
  else results.innerHTML = html ||
    `<div class="empty"><strong>${savedOnly ? 'В избранном пока нет подходящих материалов.' : 'По выбранным условиям ничего не найдено.'}</strong><p>Измените запрос или снимите ограничения.</p><button class="subtle" data-clear-filters>Снять ограничения</button></div>`;
  $('more').hidden = rows.length <= visible;
}
$('layouts').onclick = e => {
  const button = e.target.closest('button[data-layout]');
  if (!button || views[layoutTab()] === button.dataset.layout) return;
  views[layoutTab()] = button.dataset.layout;
  remember('rama-layout-' + layoutTab(), views[layoutTab()]);
  paintResults();
};
$('groupBy').onchange = e => {
  groupEnabled = e.target.checked;
  remember('rama-group', groupEnabled ? '1' : '0');
  paintResults();
};
$('results').addEventListener('toggle', e => {
  const details = e.target;
  if (details.matches('.record-info') && details.isConnected) {
    const id = details.dataset.record;
    if (details.open) {
      expandedVideos.add(id);
      if (!details.querySelector('.record-content')) details.insertAdjacentHTML('beforeend',recordContent(id));
    } else {
      expandedVideos.delete(id);
      details.querySelector('.record-content')?.remove();
    }
    return;
  }
  if (!e.target.matches('.video-group') || !e.target.isConnected) return;
  if (e.target.open) closedGroups.delete(e.target.dataset.video);
  else closedGroups.add(e.target.dataset.video);
}, true);
$('groupTools').onclick = e => {
  const button = e.target.closest('button');
  if (!button) return;
  const open = button.id === 'expandAll';
  if (videoResults()) {
    expandedVideos.clear();
    if (open) for (const item of last) expandedVideos.add(item.video);
    for (const record of $('results').querySelectorAll('.record-info')) record.open=open;
    return;
  }
  closedGroups.clear();
  if (!open) for (const items of groupedResults) closedGroups.add(items.key ?? items[0].video);
  for (const group of $('results').querySelectorAll('details')) group.open = open;
};
function filterChips() {
  const filters = [
    ...(archive.enabled ? archive.chips() : []),
    ['source',vidMap.get(source)?.title], ['person', person], ['category',catMap.get(category)?.name],
    ['section',db.sections.find(s => s.id === section)?.name],
    ['search',$('search').value],
    ['kind',mode === 'items' && !savedOnly && $('kind').value !== 'all' && $('kind').selectedOptions[0].textContent],
    ['scope',mode === 'items' && $('scope').value === 'context' && $('scope').selectedOptions[0].textContent]
  ].filter(([,label]) => label);
  $('activeFilters').innerHTML = filters.map(([key,label]) => `<button class="chip" data-remove="${key}" aria-label="Снять фильтр: ${safe(label)}">${safe(label)} ×</button>`).join(' ');
  $('filterToggle').textContent = filters.length ? 'Фильтры · '+filters.length : 'Фильтры';
  $('activeFilters').hidden = !filters.length;
  $('clearFilters').hidden = !filters.length;
}
$('activeFilters').onclick = e => {
  const key = e.target.closest('button')?.dataset.remove;
  if (!key) return;
  if(archive.enabled)archive.remove(key);
  if (key === 'category') category='';
  if (key === 'section') section='';
  if (key === 'person') person='';
  if (key === 'source') source='';
  if (key === 'search') $('search').value='';
  if (key === 'scope') $('scope').value='topic';
  if (key === 'kind') $('kind').value='all';
  limit=24; categories(); render(true);
};
function render(navigate=false){
  clearTimeout(searchTimer);
  archive.activate(archiveActive());
  const collection = videoResults() && !category && !section && !person && !source && !$('search').value && !directoryOpen;
  if (collection) $('allVideos').setAttribute('aria-current','page');
  else $('allVideos').removeAttribute('aria-current');
  const shareTopic=$('shareTopic');
  shareTopic.hidden=!(category || section);
  if (!shareTopic.hidden) {
    shareTopic.dataset.shareUrl=category
      ? (category.split('-').includes('seminar')?'seminars/':'topics/')+encodeURIComponent(category)+'/'
      : 'sections/'+encodeURIComponent(section)+'/';
    shareTopic.dataset.shareTitle=category?catMap.get(category).name:db.sections.find(row=>row.id===section).name;
  }
  const viewTitle = directoryOpen ? 'Личности' : collection ? 'Все видео' : '';
  document.title = viewTitle ? viewTitle + ' · Центр изучения варнашрамы «Рама»' : 'Центр изучения варнашрамы «Рама» — Библиотека видео';
  for (const chip of $('quick').querySelectorAll('[data-shortcut]')) {
    const active = chip.hash === '#cat='+category || chip.hash === '#section='+section || directoryOpen && chip.hash === '#directory=people';
    if (active) chip.setAttribute('aria-current','page'); else chip.removeAttribute('aria-current');
  }
  $('peopleDirectory').hidden=!directoryOpen;
  $('catalogPage').hidden=directoryOpen;
  if(directoryOpen){
    $('peopleNav').setAttribute('aria-current','page');
    return;
  }
  $('peopleNav').removeAttribute('aria-current');
  const selectedPerson=people.get(person);
  const ts=tokens($('search').value),kind=$('kind').value,sort=$('sort').value;
  const full = videoResults();
  let pool = full ? videoIndex : index;
  if (savedOnly) pool = [...index,...videoIndex].filter(i=>bookmarks.has(i.id));
  function matches(i) {
    return (!source || i.video===source)
      && (!selectedPerson || (i.id.startsWith('video:') ? selectedPerson.videos.has(i.video) : selectedPerson.items.has(i.id)))
      && (!category || i.cats?.includes(category)) && (!section || inSection(i,section));
  }
  let list = pool.filter(i=>matches(i) && (savedOnly || full || kind==='all' || i.type===kind)
    && (savedOnly || full || i.type!=='service' || selectedPerson || ts.length))
    .map(i=>({i,s:score(i,ts)})).filter(row=>row.s>=0);
  let sortedByEvent=false;
  if (archive.enabled) {
    if (full) {
      const rows = archive.filter(index.filter(matches).map(i=>({i})));
      const eventOrder = archive.sortRows(rows,sort);
      const allowed = new Set(rows.map(row=>row.i.video));
      const selected = new Map(list.map(row=>[row.i.video,row]));
      list = [...allowed].filter(id=>selected.has(id)).map(id=>selected.get(id));
      sortedByEvent = eventOrder;
    } else list = archive.filter(list);
  }
  if(!sortedByEvent && !(archive.enabled && !full && archive.sortRows(list,sort)))list.sort((a,b)=>sort==='old'?String(a.i.v.date).localeCompare(String(b.i.v.date))||((a.i.seconds??0)-(b.i.seconds??0)):sort==='new'?String(b.i.v.date).localeCompare(String(a.i.v.date))||((a.i.seconds??0)-(b.i.seconds??0)):b.s-a.s||String(b.i.v.date).localeCompare(String(a.i.v.date))||((a.i.seconds??0)-(b.i.seconds??0)));last=list.map(x=>x.i);$('heading').textContent=savedOnly?'Избранное':source?vidMap.get(source).title:person?person:category?catMap.get(category)?.name:section?db.sections.find(s=>s.id===section)?.name:full?'Все видео':'Все материалы';$('count').textContent=`Найдено: ${last.length.toLocaleString('ru-RU')}`;$('modeLabel').textContent=savedOnly?'ЛИЧНАЯ КОЛЛЕКЦИЯ':mode==='videos'?'ВИДЕО':'КАТАЛОГ';groupedResults=undefined;paintResults();$('fragments').classList.toggle('active',!savedOnly&&mode==='items');$('videos').classList.toggle('active',!savedOnly&&mode==='videos');$('kind').disabled=mode==='videos'||savedOnly;$('scope').disabled=mode==='videos';$('savedCount').textContent=bookmarks.size?'('+bookmarks.size+')':'';filterChips();const p=new URLSearchParams();archive.write(p);if(source)p.set('source',source);if(person)p.set('person',person);if(savedOnly)p.set('saved','1');if($('search').value)p.set('q',$('search').value);if(category)p.set('cat',category);if(section)p.set('section',section);if(mode==='videos')p.set('mode',mode);if(kind!=='all'&&mode==='items')p.set('kind',kind);if(sort!=='relevance')p.set('sort',sort);if($('scope').value==='context')p.set('scope','context');const hash=p.size?'#'+p:'';
if(location.hash!==hash){
  const method=navigate===true?'pushState':'replaceState';
  try{history[method](null,'',location.pathname+location.search+hash)}catch{}
}}
function reset(){clearFilters();category='';section='';mode='items';$('sort').value='relevance';categories();render(true)}
function clearInPlace(){
  clearFilters();
  category='';
  section='';
  categories();
  render(true)
}
function videoSharePath(item) {
  const path='video/'+encodeURIComponent(item.video)+'/';
  if (item.seconds != null) return path+'?t='+item.seconds;
  return item.id.startsWith('video:') ? path : path+'#'+encodeURIComponent(item.id);
}
function openItem(id){const i=byId.get(id);if(!i)return;const v=i.v||{},items=(chapters.get(i.video)||[]).filter(c=>c.seconds!=null).sort((a,b)=>a.seconds-b.seconds);const refs=(v.references||[]).filter(r=>linkURL(r.url));$('detailContent').innerHTML=`<h2 id="detailTitle">${safe(i.title)}</h2><p class="meta">${safe(v.title||'')} · ${safe(v.date||'')}</p><iframe title="Видео YouTube" src="https://www.youtube-nocookie.com/embed/${encodeURIComponent(i.video)}${i.seconds == null ? '' : '?start='+Number(i.seconds)}" allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture; web-share" allowfullscreen></iframe>${i.keywords?.length?`<div class="tags">${i.keywords.map(k=>archive.enabled?keywordButton(i,k):`<button data-query="${safe(k)}">${safe(k)}</button>`).join('')}</div>`:''}<p><a class="primary" href="${safe(yt(i.video,i.seconds))}" target="_blank" rel="noopener noreferrer">Открыть на YouTube ↗</a> <button class="subtle" data-share-url="${safe(videoSharePath(i))}" data-share-title="${safe(i.title)}">Поделиться</button></p>${items.length?`<h3>Все тайм-коды (${items.length})</h3>${items.map(c=>`<div class="chapter"><a href="${safe(yt(c.video,c.seconds))}" target="_blank" rel="noopener noreferrer">${timestamp(c.seconds)}</a><span>${safe(c.title)}</span></div>`).join('')}`:'<p class="meta">Это видео не имеет тайм-кодов в исходной базе.</p>'}${v.descriptions?.length?`<h3>Описания</h3>${v.descriptions.map(d=>`<p>${safe(d)}</p>`).join('')}`:''}${refs.length?`<div class="detailslinks"><h3>Дополнительные источники</h3>${refs.map(r=>`<p><a href="${safe(linkURL(r.url))}" target="_blank" rel="noopener noreferrer">${safe(r.text||r.url)} ↗</a></p>`).join('')}<small>Доступность внешних источников не проверена.</small></div>`:''}`;$('detail').showModal()}
$('close').onclick=()=>$('detail').close();$('detail').addEventListener('close',()=>$('detailContent').innerHTML='');document.addEventListener('click',e=>{const place=e.target.closest('[data-event-place]');if(place){if($('detail').open)$('detail').close();archive.toggleCity(place.dataset.eventPlace);return}const b=e.target.closest('[data-cat],[data-section-select],[data-open],[data-bookmark],[data-query],[data-clear-filters]');if(!b)return;if(b.dataset.clearFilters!==undefined){clearInPlace();return}if(b.dataset.cat!==undefined){setCategory(b.dataset.cat);return}if(b.dataset.sectionSelect!==undefined){setSection(b.dataset.sectionSelect);return}if(b.dataset.open)openItem(b.dataset.open);if(b.dataset.bookmark){const id=b.dataset.bookmark;bookmarks.has(id)?bookmarks.delete(id):bookmarks.add(id);try{localStorage.setItem('rama-favorites',JSON.stringify([...bookmarks]))}catch{}
if(savedOnly)render();else{
  const on=bookmarks.has(id);
  for(const b of $('results').querySelectorAll('[data-bookmark="'+CSS.escape(id)+'"]')){
  b.setAttribute('aria-pressed',String(on));
  b.setAttribute('aria-label',on?'Удалить из избранного':'В избранное');
  b.classList.toggle('on',on);b.textContent=on?'★':'☆';}
  $('savedCount').textContent=bookmarks.size?'('+bookmarks.size+')':'';
}}if(b.dataset.query){if($('detail').open)$('detail').close();clearFilters();$('search').value=b.dataset.query.includes(' ')?'"'+b.dataset.query+'"':b.dataset.query;category='';section='';mode='items';categories();render(true);jumpResults()}});
$('quick').onclick = e => {
  const link = e.target.closest('a');
  if (!link || e.ctrlKey || e.metaKey || e.shiftKey || e.altKey) return;
  e.preventDefault();
  const params=new URLSearchParams(link.hash.slice(1));
  if (params.has('directory')) {location.hash=link.hash; return}
  mode='items'; $('kind').value='all';
  if (params.has('cat')) setCategory(params.get('cat')); else setSection(params.get('section'));
};
$('search').oninput=()=>{limit=24;clearTimeout(searchTimer);searchTimer=setTimeout(render,130)};$('search').onkeydown=e=>{if(e.key==='Enter'){render();jumpResults()}};$('clear').onclick=()=>{$('search').value='';limit=24;render();$('search').focus()};$('kind').onchange=()=>{expandedVideos.clear();limit=24;categories();render(true)};
$('sort').onchange=$('scope').onchange=()=>{limit=24;render()};$('more').onclick=()=>{limit+=24;paintResults(true)};$('home').onclick=$('reset').onclick=reset;$('clearFilters').onclick=clearInPlace;$('saved').onclick=()=>{const was=savedOnly;clearFilters();category='';section='';mode='items';$('sort').value='relevance';savedOnly=!was;categories();render(true);jumpResults()};$('fragments').onclick=()=>{mode='items';savedOnly=false;$('kind').value='all';limit=24;categories();render(true)};$('videos').onclick=()=>{expandedVideos.clear();mode='videos';savedOnly=false;$('kind').value='all';limit=24;categories();render(true)};$('theme').onclick=()=>{document.body.classList.toggle('light');try{localStorage.setItem('rama-theme',document.body.classList.contains('light')?'light':'dark')}catch{}};const mq=matchMedia('(max-width:850px), (max-height:500px) and (pointer:coarse)');
let topicOpener;
function closeTopics() {
  if ($('topicDrawer').open) {
    $('topicDrawer').close();
    $('mobileCategories').setAttribute('aria-expanded','false');
  }
}
function restoreTopics() {
  if ($('topicDrawer').open) return;
  $('topicRail').insertBefore($('categoryPanel'),$('topicDrawer'));
  $('categoryPanel').hidden=mq.matches;
  $('mobileCategories').setAttribute('aria-expanded','false');
  topicOpener?.focus({preventScroll:true});
}
function openTopics(button) {
  if (directoryOpen) reset();
  if (!mq.matches) {
    $('topicRail').scrollIntoView({block:'start'});
    $('peopleNav').focus({preventScroll:true});
    return;
  }
  topicOpener=button;
  $('topicDrawer').append($('categoryPanel'));
  $('categoryPanel').hidden=false;
  $('topicDrawer').showModal();
  $('mobileCategories').setAttribute('aria-expanded','true');
  $('drawerClose').focus();
}
$('topicDrawer').addEventListener('close',restoreTopics);
$('drawerClose').onclick=closeTopics;
$('drawerReset').onclick=()=>{reset();jumpResults()};
$('mobileCategories').onclick=e=>openTopics(e.currentTarget);
$('allTopics').onclick=e=>openTopics(e.currentTarget);
function responsive() {
  closeTopics();
  $('categoryPanel').hidden=mq.matches;
}
mq.addEventListener('change',responsive);
responsive();
$('filterToggle').onclick=()=>{
  const open=$('filterFields').classList.toggle('expanded');
  $('filterToggle').setAttribute('aria-expanded',String(open));
};
$('allVideos').onclick=e=>{
  if (e.ctrlKey || e.metaKey || e.shiftKey || e.altKey) return;
  e.preventDefault();
  clearFilters(); category=''; section=''; mode='videos'; expandedVideos.clear();
  $('sort').value='new'; categories(); render(true); jumpResults();
  $('heading').focus({preventScroll:true});
};
$('mobileHome').onclick=()=>{reset();window.scrollTo(0,0)};
$('mobileSearch').onclick=()=>{if(directoryOpen)reset();$('search').scrollIntoView({block:'center'});$('search').focus({preventScroll:true})};
$('mobileSaved').onclick=()=>$('saved').click();
new ResizeObserver(([entry])=>{
  document.documentElement.style.setProperty('--header-height',entry.target.offsetHeight+'px');
}).observe(document.querySelector('header'));
new ResizeObserver(([entry])=>{
  document.documentElement.style.setProperty('--bottom-height',entry.target.offsetHeight+'px');
}).observe(document.querySelector('.bottom-bar'));
stats();categories();render();$('workspace').classList.add('ready');focusPersonView();
