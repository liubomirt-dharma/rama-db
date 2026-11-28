// Публичные метки населённых пунктов. В меню попадают только встречающиеся в разделе.
const settlementNames = [
  ['Белгород-Днестровский','Білгород-Дністровський','Bilhorod-Dnistrovskyi'],
  ['Белополье','Білопілля','Bilopillia'], ['Днепр','Дніпро','Dnipro','Dnepr'],
  ['Дымер','Димер','Dymer'], ['Запорожье','Запоріжжя','Zaporizhzhia','Zaporozhye'],
  ['Златополь','Златопіль','Zlatopil'], ['Ивано-Франковск','Івано-Франківськ','Ivano-Frankivsk'],
  ['Каменское','Кам’янське','Kamianske'], ['Камышеваха','Комишуваха','Komyshuvakha'],
  ['Киев','Київ','Kyiv','Kiev'], ['Краматорск','Краматорськ','Kramatorsk'],
  ['Кременчуг','Кременчук','Kremenchuk'], ['Кривой Рог','Кривий Ріг','Kryvyi Rih'],
  ['Кропивницкий','Кропивницький','Kropyvnytskyi'], ['Луцк','Луцьк','Lutsk'],
  ['Львов','Львів','Lviv'], ['Марганец','Марганець','Marhanets'],
  ['Николаев','Миколаїв','Mykolaiv'], ['Новая Водолага','Нова Водолага','Nova Vodolaha'],
  ['Новоплатоновка','Новоплатонівка','Novoplatonivka'], ['Одесса','Одеса','Odesa','Odessa'],
  ['Прилуки','Прилуки','Pryluky'], ['Ровно','Рівне','Rivne'],
  ['Степногорск','Степногірськ','Stepnohirsk'], ['Сумы','Суми','Sumy'],
  ['Тернополь','Тернопіль','Ternopil'], ['Харьков','Харків','Kharkiv','Kharkov'],
  ['Херсон','Kherson'], ['Чернигов','Чернігів','Chernihiv'], ['Черновцы','Чернівці','Chernivtsi'],
  ['Чернеччина','Chernechchyna']
];

// Источник — заголовок записи с указанным ID. "/" разделяет границы периода,
// "," перечисляет отдельные дни. Частичная дата сохраняет исходную точность.
const shellingDates = {
  'v001-t000436':['2026-11-18/2026-11-22','с 18 по 22 ноября 2026 года'],
  'v002-t001140':['2026-11-08/2026-11-13','8–13 ноября 2026'],
  'v003-t000548':['2026-11-02','2 ноября 2026 года'],
  'v016-t000281':['2026-07-16','16 июля 2026 года'],
  'v017-t000400':['2026-07-03','3 июля 2026'],
  'v017-t001825':['2026-07-06','6 июля 2026'],
  'v018-t000103':['2026-07-02','2 июля 2026'],
  'v026-t003021':['2026-04-06','6 апреля 2026'],
  'v026-t004309':['2026-04-25','25 апреля 2026'],
  'v053-t002325':['2025','2025'],
  'v066-t001319':['2025-09-20','20.09.2025'],
  'v068-t000535':['2025-09-07','07.09.2025'],
  'v069-t000344':['2025-08-28,2025-08-30','28 и 30 августа 2025 года'],
  'v094-t000398':['2025-04-23,2025-04-24','23/24.04.2025'],
  'v127-t008494':['2024-09-04','4 сентября 2024'],
  'v084-full':['2025-06-23,2025-06-24','23/24.06.2025'],
  'v086-full':['2025-06-17,2025-06-20','17/20.06.2025']
};

// Ручные сопоставления: период, проверочная карточка, основание.
// Диапазон сводки относится ко всему обзору.
const shellingContextDates = {
  'v001-t000882': ['2026-11-18/2026-11-22','v001-t000436','Кадры из ноябрьской сводки'],
  'v001-t001314': ['2026-11','v001-t000436','Продолжение ноябрьской сводки'],
  'v001-t001813': ['2026-11-18/2026-11-22','v001-t000436','Итоги ноябрьской сводки'],
  'v002-t001451': ['2026-11-08/2026-11-13','v002-t001140','Кадры последствий из ноябрьской хроники'],
  'v017-t002440': ['2026-07-06','v017-t001825','Продолжение рассказа об атаке на Киев'],
  'v085-t000478': ['2025-06-17,2025-06-20','v086-full','Те же города и оба июньских дня в описании киртана']
};

// Дни из книги v6 для сведений с предположительным годом.
const shellingMonthDays = {
  'v004-t000292': ['10-29'],
  'v004-t000567': ['10-29'],
  'v004-t000953': ['10-29'],
  'v007-t000373': ['10-07'],
  'v007-t001638': ['10-07'],
  'v013-t000179': ['08-20'],
  'v015-t000082': ['07-19'],
  'v020-t000110': ['06-15'],
  'v057-t000368': ['12-01'],
  'v058-t000480': ['11-25', '11-29'],
  'v092-t000520': ['05-07'],
  'v096-t000673': ['04-04'],
  'v100-t000595': ['03-06']
};

function eventInterval(spec) {
  const [start, end=start] = spec.split('/');
  const [year, month=12, day] = end.split('-').map(Number);
  const lastDay = day ?? new Date(Date.UTC(year, month, 0)).getUTCDate();
  return {
    start: (start+'-01-01').slice(0,10),
    end: [year,String(month).padStart(2,'0'),String(lastDay).padStart(2,'0')].join('-')
  };
}

function yearsCovered(intervals) {
  const years = new Set();
  for (const range of intervals) {
    for (let y=Number(range.start.slice(0,4)); y<=Number(range.end.slice(0,4)); y++) years.add(y);
  }
  return years;
}

function eventLabel(spec) {
  const format = value => {
    if(value.length===4) return value+' год';
    const parts = value.split('-').map(Number);
    const date = new Date(Date.UTC(parts[0],parts[1]-1,parts[2] || 1));
    const options = {timeZone:'UTC',year:'numeric',month:'long'};
    if(parts.length===3) options.day='numeric';
    return date.toLocaleDateString('ru-RU',options)+(parts.length===2?', день не установлен':'');
  };
  return spec.split(',').map(range=>range.split('/').map(format).join(' — ')).join(' и ');
}

function createShellingIndex(items, videos) {
  const collator = new Intl.Collator('ru');
  const canonical = new Map();
  const aliases = new Map();
  const normalize = s => s.normalize('NFKC').toLowerCase().replace(/ё/g,'е').replace(/[’']/g,'');
  for (const names of settlementNames) {
    aliases.set(names[0], names.map(normalize));
    for (const name of names) canonical.set(normalize(name),names[0]);
  }
  const metadata = new Map(), citySet = new Set(), yearSet = new Set();
  for (const item of items.filter(i => i.cats.includes('shelling'))) {
    const cities = [...new Set(item.keywords.map(k => canonical.get(normalize(k))).filter(Boolean))].sort(collator.compare);
    for (const city of cities) citySet.add(city);
    const evidence = shellingContextDates[item.id];
    const [documented='', quote=''] = shellingDates[item.id] || [evidence?.[0]];
    const publicationYear = /^(\d{4})-\d{2}-\d{2}$/.exec(videos.get(item.video)?.date)?.[1];
    const inferred = !documented && Boolean(publicationYear);
    let spec = documented;
    if (inferred) {
      const days = shellingMonthDays[item.id];
      spec = days ? days.map(day => publicationYear+'-'+day).join(',') : publicationYear;
    }

    const intervals = spec ? spec.split(',').map(eventInterval) : [];
    const years = yearsCovered(intervals);
    for (const y of years) yearSet.add(y);
    metadata.set(item.id,{cities, years, spec, quote, evidence, inferred, start:intervals[0]?.start,end:intervals.at(-1)?.end});
  }
  return {metadata, cities:[...citySet].sort(collator.compare), years:[...yearSet].sort((a,b)=>b-a),
    canonical:name=>canonical.get(normalize(name)), matches:(city,q)=>aliases.get(city).some(a=>a.includes(normalize(q.trim()))), compare:collator.compare};
}

function createShellingPanel(items, videos, onChange) {
  const data = createShellingIndex(items, videos);
  const get = id=>document.getElementById(id);
  const sorts = {'event-new':'Сначала новые события','event-old':'Сначала старые события','city-asc':'По городам: А–Я','city-desc':'По городам: Я–А'};
  let enabled=false, period='all', year='', group='none';
  const selected = new Set();
  const actualYear = () => {
    const now = new Date().getFullYear();
    return period==='current' ? now : period==='previous' ? now-1 : period==='year' && year ? Number(year) : null;
  };
  function resetFilters() { period='all'; year=''; selected.clear(); }
  function activate(active) {
    if(enabled===active) return;
    enabled=active;
    get('eventPanel').hidden=!active;
    get('eventGrouping').hidden=!active;
    if(active) {
      for(const [id,label] of Object.entries(sorts)) get('sort').add(new Option(label,id));
    } else {
      resetFilters(); group='none'; get('cityMenu').open=false; get('citySearch').value='';
      if(Object.hasOwn(sorts,get('sort').value)) get('sort').value='relevance';
      for(const opt of [...get('sort').options]) if(Object.hasOwn(sorts,opt.value)) opt.remove();
    }
  }
  function read(params) {
    resetFilters();
    group='none';
    if(!enabled) return;
    const requested=params.get('period');
    if(['current','previous','year'].includes(requested)) period=requested;
    year=params.get('year') || '';
    if(year && !data.years.includes(Number(year))){year='';if(period==='year') period='all'}
    for(const slug of params.getAll('city')) {
      const city=data.canonical(slug);
      if(data.cities.includes(city)) selected.add(city);
    }
    if(['video','year','date','city'].includes(params.get('group'))) group=params.get('group');
    if(Object.hasOwn(sorts,params.get('sort'))) get('sort').value=params.get('sort');
  }
  function write(params) {
    if(!enabled) return;
    if(period!=='all') params.set('period',period);
    if(period==='year' && year) params.set('year',year);
    for(const c of selected) params.append('city',c);
    if(group!=='none') params.set('group',group);
  }
  const cityCounts=new Map();
  function drawCities() {
    const box=get('cityList');
    const focusCity=document.activeElement?.dataset.eventCity;
    box.replaceChildren();
    for(const city of data.cities.filter(c=>data.matches(c,get('citySearch').value))) {
      const label=document.createElement('label'), input=document.createElement('input');
      input.type='checkbox'; input.dataset.eventCity=city; input.checked=selected.has(city);
      const count=document.createElement('small'); count.textContent=cityCounts.get(city)||0;
      label.append(input,document.createTextNode(city),count); box.append(label);
      if(focusCity===city) input.focus({preventScroll:true});
    }
    if(!box.childElementCount) box.textContent='Населённый пункт не найден';
  }
  function filter(rows) {
    const target=actualYear(), years=new Map(), result=[];
    cityCounts.clear();
    for(const row of rows) {
      const m=data.metadata.get(row.i.id);
      const byYear=target===null || m.years.has(target);
      const byCity=!selected.size || m.cities.some(c=>selected.has(c));
      if(byYear) for(const c of m.cities) cityCounts.set(c,(cityCounts.get(c)||0)+1);
      if(byCity) for(const y of m.years) years.set(y,(years.get(y)||0)+1);
      if(byYear && byCity) result.push(row);
    }
    get('eventPeriod').value=period;
    const picker=get('eventYear');
    picker.replaceChildren(new Option('Год…',''),...data.years.map(y=>new Option(y+' ('+(years.get(y)||0)+')',y)));
    picker.value=year; picker.hidden=period!=='year';
    get('cityCaption').textContent=selected.size?'Города ('+selected.size+')':'Все города';
    get('eventReset').hidden=target===null && !selected.size;
    get('eventGroup').value=group;
    drawCities();
    return result;
  }
  function ordered(a,b,direction,compare) {
    if(!a || !b) return Number(!a)-Number(!b);
    return compare(a,b)*direction;
  }
  function sortRows(rows,sort) {
    if(!Object.hasOwn(sorts,sort)) return false;
    const cityKey=m=>m.cities.find(c=>selected.has(c)) || m.cities[0];
    rows.sort((a,b)=>{
      const x=data.metadata.get(a.i.id), y=data.metadata.get(b.i.id);
      if(sort.startsWith('city')){
        const cmp=ordered(cityKey(x),cityKey(y),sort==='city-asc'?1:-1,data.compare);
        if(cmp) return cmp;
      }
      const field=sort==='event-old'?'start':'end';
      return ordered(x[field],y[field],sort==='event-old'?1:-1,data.compare);
    });
    return true;
  }
  function groupRows(list) {
    const map=new Map(), target=actualYear();
    for(const item of list) {
      const m=data.metadata.get(item.id);
      const keys=group==='city'?m.cities.filter(c=>!selected.size||selected.has(c)):
        group==='year'?[...m.years].filter(y=>target===null||target===y):m.spec?[m.spec+(m.inferred?'~':'')]:[];
      for(const k of keys.length?keys:['']) {
        if(!map.has(k)) map.set(k,{key:group+':'+k,label:group==='date' && k?eventLabel(m.spec)+(m.inferred?' · год по публикации':''):String(k),items:[]});
        map.get(k).items.push(item);
      }
    }
    const unknown=map.get('');
    map.delete('');
    const keys=[...map.keys()].sort((a,b)=>group==='year'?b-a:data.compare(a,b)*(group==='date'?-1:1));
    const groups=keys.map(k=>map.get(k));
    if(unknown){unknown.label=group==='city'?'Населённый пункт не установлен':'Дата события не установлена';groups.push(unknown)}
    return groups;
  }
  function toggleCity(c) {
    if(!enabled || !data.cities.includes(c)) return;
    if(selected.has(c)) selected.delete(c); else selected.add(c);
    onChange();
  }
  get('eventPeriod').onchange=e=>{
    period=e.target.value;
    onChange();
  };
  get('eventYear').onchange=e=>{year=e.target.value;if(!year)period='all';onChange()};
  get('eventGroup').onchange=e=>{group=e.target.value;onChange()};
  get('eventReset').onclick=()=>{resetFilters();onChange()};
  get('cityClear').onclick=()=>{selected.clear();onChange()};
  get('citySearch').oninput=drawCities;
  get('cityList').onchange=e=>toggleCity(e.target.dataset.eventCity);
  document.addEventListener('click',e=>{if(!get('cityMenu').contains(e.target)) get('cityMenu').open=false});
  get('cityMenu').addEventListener('keydown',e=>{if(e.key==='Escape'){get('cityMenu').open=false;get('cityMenu').querySelector('summary').focus()}});
  return {activate, read, write, filter, sortRows, groupRows, toggleCity,
    get enabled(){return enabled},get group(){return group},get selected(){return selected},
    city:name=>data.canonical(name),meta:id=>data.metadata.get(id),
    chips:()=>[...(actualYear()===null?[]:[['eventPeriod',actualYear()+' год']]),...[...selected].map(c=>['city:'+c,c])],
    remove(key){if(key==='eventPeriod'){period='all';year=''}else if(key.startsWith('city:'))selected.delete(key.slice(5))}
  };
}
