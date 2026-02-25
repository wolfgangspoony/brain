Beat Atlas Redesign Inspired by Sunrise Robotics

Sunrise Robotics - Intelligent robotics transforming manufacturing..html

HTML 85.88KB

THINGY.html

HTML 21.66KB

THINGY is great but modify based on inspiration of sunrise robots website and make new thingy with improved visuals thanks

We are going to create a new version of THINGY (Beat Atlas) with improved visuals inspired by the Sunrise Robotics website.  
The Sunrise Robotics website has a modern, clean, and high-tech aesthetic with smooth animations and a sophisticated color scheme.

Steps:

1. We'll keep the core functionality of THINGY (the beat browsing, filtering, playing, etc.) but update the visual design.
    
2. We'll adopt a color scheme and typography that aligns with the Sunrise Robotics website.
    
3. We'll try to incorporate some of the design elements and layout principles from the Sunrise Robotics website.
    

Observations from Sunrise Robotics:

- Color palette: dark backgrounds, with accents of orange (#FA6147) and light blue (#36A3EB) and white.
    
- Typography: Clean, sans-serif fonts. Sunrise uses a custom font but we can use Inter (which is already in THINGY) or a similar one.
    
- Layout: Spacious, with a focus on large headings and clear sections.
    
- Animations: Smooth transitions and scroll effects (we might not do the complex scroll animations but can add some subtle ones).
    

Since we are not changing the functionality, we will focus on the CSS and HTML structure for the visual update.

Let's break down the changes:

1. Update the color scheme to match the Sunrise Robotics website.
    
    - Background: dark (like #0E0E08 or #0b0b0d from THINGY is already dark, but we might adjust)
        
    - Accent colors: Use orange (#FA6147) and blue (#36A3EB) for buttons, highlights, etc.
        
2. Update the typography to be more modern and clean. We already have Inter, which is good.
    
3. Redesign the header and navigation to be more minimal, perhaps with a fixed header.
    
4. Redesign the beat cards to have a more modern look, maybe with a glassmorphism effect or subtle gradients.
    
5. Update the player to match the new color scheme and make it more sleek.
    
6. Add some subtle animations (like on hover for cards, buttons) to make the interface feel more dynamic.
    
7. Consider the overall spacing and layout to be more spacious and aligned.
    

Let's define a new color scheme in :root based on Sunrise Robotics:

--bg: #0E0E08; (or keep #0b0b0d, but adjust if needed)  
--card-bg: rgba(255, 255, 255, 0.05); (for glassmorphism)  
--text: #E4E4DD; (light off-white)  
--accent-1: #FA6147; (orange)  
--accent-2: #36A3EB; (blue)

We'll adjust the existing THINGY styles step by step.

Note: We are not going to implement the complex scroll animations of Sunrise Robotics because that would require a major rewrite and might not fit the beat store concept.

Let's start by updating the CSS variables and then restyle each component.

# Beat Atlas Redesign - Inspired by Sunrise Robotics

I've analyzed both websites and will create a redesigned Beat Atlas that incorporates the modern, high-tech aesthetic of Sunrise Robotics while maintaining the core functionality of the music beat marketplace.

html

<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width,initial-scale=1" />
<title>Beat Atlas — Premium Beats & Packs</title>
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap" rel="stylesheet">
<style>
  :root {
    --bg-dark: #0E0E08;
    --bg-card: rgba(255, 255, 255, 0.03);
    --bg-glass: rgba(255, 255, 255, 0.05);
    --text-primary: #E4E4DD;
    --text-muted: #9AA0A6;
    --accent-orange: #FA6147;
    --accent-blue: #36A3EB;
    --accent-yellow: #F1EA65;
    --accent-red: #F35F5F;
    --radius: 12px;
    --max-width: 1200px;
    --transition: 0.3s cubic-bezier(0.4, 0, 0.2, 1);
    --shadow: 0 10px 40px rgba(0, 0, 0, 0.2);
    --border: 1px solid rgba(255, 255, 255, 0.06);
  }
  
  * { box-sizing: border-box; margin: 0; padding: 0; }
  html, body { height: 100%; }
  
  body {
    margin: 0;
    min-height: 100%;
    font-family: Inter, system-ui, -apple-system, "Segoe UI", Roboto, "Helvetica Neue", Arial;
    background: var(--bg-dark);
    color: var(--text-primary);
    -webkit-font-smoothing: antialiased;
    -moz-osx-font-smoothing: grayscale;
    line-height: 1.5;
  }

  /* Sunrise-inspired gradient backgrounds */
  .gradient-bg {
    background: linear-gradient(180deg, #050506 0%, #0E0E08 40%);
  }
  
  .accent-gradient {
    background: linear-gradient(90deg, var(--accent-orange), var(--accent-blue));
    -webkit-background-clip: text;
    background-clip: text;
    color: transparent;
  }

  /* Layout */
  .wrap {
    max-width: var(--max-width);
    margin: 0 auto;
    padding: 0 20px;
  }
  
  /* Header - Inspired by Sunrise */
  header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 24px 0;
    margin-bottom: 32px;
    position: relative;
  }
  
  .brand {
    display: flex;
    align-items: center;
    gap: 12px;
  }
  
  .logo {
    font-weight: 800;
    font-size: 24px;
    letter-spacing: -0.8px;
    background: linear-gradient(90deg, var(--accent-orange), var(--accent-blue));
    -webkit-background-clip: text;
    background-clip: text;
    color: transparent;
  }
  
  .tagline {
    color: var(--text-muted);
    font-weight: 500;
    font-size: 14px;
    padding-left: 12px;
    border-left: 1px solid rgba(255, 255, 255, 0.1);
  }
  
  nav {
    display: flex;
    gap: 20px;
    align-items: center;
  }
  
  nav a {
    color: var(--text-muted);
    text-decoration: none;
    font-weight: 600;
    font-size: 14px;
    padding: 8px 12px;
    border-radius: 8px;
    transition: var(--transition);
  }
  
  nav a:hover {
    color: var(--text-primary);
    background: var(--bg-glass);
  }

  /* Hero Section - Inspired by Sunrise */
  .hero {
    margin-bottom: 48px;
    max-width: 800px;
  }
  
  .hero h1 {
    font-size: 40px;
    font-weight: 800;
    line-height: 1.2;
    margin-bottom: 16px;
    background: linear-gradient(90deg, #E4E4DD, #9AA0A6);
    -webkit-background-clip: text;
    background-clip: text;
    color: transparent;
  }
  
  .hero p {
    color: var(--text-muted);
    font-size: 18px;
    line-height: 1.6;
  }

  /* Controls - Enhanced design */
  .controls {
    display: flex;
    gap: 16px;
    align-items: center;
    margin: 32px 0;
    flex-wrap: wrap;
    background: var(--bg-glass);
    padding: 16px;
    border-radius: var(--radius);
    border: var(--border);
  }
  
  .search {
    display: flex;
    align-items: center;
    background: rgba(0, 0, 0, 0.2);
    padding: 12px 16px;
    border-radius: var(--radius);
    gap: 10px;
    flex: 1;
    min-width: 280px;
    border: var(--border);
    transition: var(--transition);
  }
  
  .search:focus-within {
    box-shadow: 0 0 0 2px var(--accent-blue);
  }
  
  .search input {
    background: transparent;
    border: 0;
    outline: none;
    color: var(--text-primary);
    font-size: 15px;
    width: 100%;
  }
  
  .search input::placeholder {
    color: var(--text-muted);
  }
  
  .filters {
    display: flex;
    gap: 8px;
    align-items: center;
    flex-wrap: wrap;
  }
  
  .chip {
    border: var(--border);
    background: transparent;
    padding: 10px 16px;
    border-radius: 999px;
    font-weight: 600;
    font-size: 14px;
    color: var(--text-muted);
    cursor: pointer;
    transition: var(--transition);
  }
  
  .chip:hover {
    transform: translateY(-2px);
    color: var(--text-primary);
    border-color: rgba(255, 255, 255, 0.1);
  }
  
  .chip.active {
    background: linear-gradient(90deg, var(--accent-orange), var(--accent-blue));
    color: #fff;
    border: 0;
    box-shadow: var(--shadow);
  }
  
  .sort-select {
    background: rgba(0, 0, 0, 0.2);
    border-radius: var(--radius);
    padding: 12px 16px;
    border: var(--border);
    color: var(--text-muted);
    font-weight: 600;
    cursor: pointer;
    transition: var(--transition);
  }
  
  .sort-select:focus {
    outline: none;
    box-shadow: 0 0 0 2px var(--accent-blue);
  }

  /* Grid - Enhanced card design */
  .grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(240px, 1fr));
    gap: 24px;
    margin-top: 24px;
  }
  
  .card {
    background: linear-gradient(180deg, rgba(255, 255, 255, 0.03), transparent);
    border-radius: var(--radius);
    overflow: hidden;
    border: var(--border);
    transition: var(--transition);
    position: relative;
  }
  
  .card:focus-within, .card:hover {
    transform: translateY(-8px);
    box-shadow: var(--shadow);
    border-color: rgba(255, 255, 255, 0.1);
  }
  
  .cover {
    aspect-ratio: 1/1;
    background-size: cover;
    background-position: center;
    position: relative;
    overflow: hidden;
  }
  
  .cover::after {
    content: '';
    position: absolute;
    inset: 0;
    background: linear-gradient(to bottom, transparent 0%, rgba(0, 0, 0, 0.5) 100%);
    opacity: 0.7;
    transition: var(--transition);
  }
  
  .card:hover .cover::after {
    opacity: 0.9;
  }
  
  .cover .play {
    position: absolute;
    inset: 0;
    display: flex;
    align-items: center;
    justify-content: center;
    opacity: 0;
    transition: var(--transition);
    cursor: pointer;
    z-index: 2;
  }
  
  .card:hover .play, .card:focus-within .play {
    opacity: 1;
  }
  
  .play button {
    width: 60px;
    height: 60px;
    border-radius: 50%;
    border: 0;
    background: linear-gradient(90deg, var(--accent-orange), var(--accent-blue));
    display: grid;
    place-items: center;
    font-size: 20px;
    color: white;
    box-shadow: 0 8px 24px rgba(54, 163, 235, 0.2);
    transition: var(--transition);
    transform: scale(0.9);
  }
  
  .card:hover .play button {
    transform: scale(1);
  }
  
  .meta {
    padding: 16px;
    display: flex;
    flex-direction: column;
    gap: 10px;
  }
  
  .title {
    font-weight: 700;
    font-size: 16px;
    line-height: 1.4;
  }
  
  .sub {
    display: flex;
    gap: 8px;
    align-items: center;
    flex-wrap: wrap;
    color: var(--text-muted);
    font-size: 14px;
  }
  
  .price {
    margin-top: 8px;
    font-weight: 800;
    color: var(--accent-orange);
    font-size: 18px;
  }
  
  .buy {
    margin-top: 12px;
    padding: 12px;
    border-radius: var(--radius);
    border: var(--border);
    background: transparent;
    color: var(--text-muted);
    font-weight: 700;
    cursor: pointer;
    transition: var(--transition);
  }
  
  .buy:hover {
    background: linear-gradient(90deg, var(--accent-orange), var(--accent-blue));
    color: #fff;
    border-color: transparent;
    transform: translateY(-2px);
  }
  
  .tag {
    padding: 6px 10px;
    border-radius: 999px;
    font-weight: 700;
    font-size: 12px;
    background: rgba(255, 255, 255, 0.05);
    color: var(--text-muted);
  }

  /* Pack badge - Enhanced */
  .pack-badge {
    position: absolute;
    top: 12px;
    left: 12px;
    padding: 8px 12px;
    border-radius: var(--radius);
    font-weight: 800;
    font-size: 12px;
    background: linear-gradient(90deg, var(--accent-yellow), var(--accent-blue));
    color: var(--bg-dark);
    z-index: 2;
    box-shadow: var(--shadow);
  }

  /* Player - Enhanced with Sunrise aesthetics */
  .player {
    position: fixed;
    left: 50%;
    transform: translateX(-50%);
    bottom: 24px;
    width: calc(100% - 40px);
    max-width: var(--max-width);
    background: linear-gradient(180deg, rgba(255, 255, 255, 0.05), rgba(255, 255, 255, 0.03));
    border-radius: 16px;
    padding: 16px 20px;
    box-shadow: 0 20px 50px rgba(0, 0, 0, 0.3);
    display: flex;
    align-items: center;
    gap: 16px;
    border: var(--border);
    z-index: 1000;
    backdrop-filter: blur(10px);
  }
  
  .player .thumb {
    width: 64px;
    height: 64px;
    border-radius: var(--radius);
    background-size: cover;
    background-position: center;
    border: var(--border);
    flex-shrink: 0;
  }
  
  .player .info {
    flex: 1;
    min-width: 0;
  }
  
  .player .track {
    font-weight: 800;
    font-size: 16px;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }
  
  .player .artist {
    color: var(--text-muted);
    font-size: 14px;
    margin-top: 4px;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }
  
  .controls-play {
    display: flex;
    align-items: center;
    gap: 12px;
  }
  
  .pv-btn {
    width: 46px;
    height: 46px;
    border-radius: var(--radius);
    border: 0;
    background: rgba(255, 255, 255, 0.05);
    color: var(--text-primary);
    font-weight: 800;
    cursor: pointer;
    transition: var(--transition);
    display: flex;
    align-items: center;
    justify-content: center;
  }
  
  .pv-btn:hover {
    background: rgba(255, 255, 255, 0.1);
  }
  
  .pv-btn.playing {
    background: linear-gradient(90deg, var(--accent-orange), var(--accent-blue));
    color: white;
    box-shadow: 0 8px 20px rgba(243, 95, 95, 0.2);
  }
  
  .progress-wrap {
    width: 320px;
    max-width: 36%;
    display: flex;
    flex-direction: column;
    gap: 8px;
  }
  
  .prog-bar {
    height: 6px;
    background: rgba(255, 255, 255, 0.05);
    border-radius: 999px;
    overflow: hidden;
  }
  
  .prog-fill {
    height: 100%;
    width: 0%;
    background: linear-gradient(90deg, var(--accent-orange), var(--accent-blue));
    border-radius: 999px;
    transition: width 0.3s ease;
  }
  
  .time {
    display: flex;
    justify-content: space-between;
    color: var(--text-muted);
    font-size: 12px;
  }

  /* Load more button - Enhanced */
  .load-more {
    display: block;
    margin: 40px auto 120px auto;
    padding: 14px 24px;
    border-radius: 999px;
    background: transparent;
    color: var(--text-muted);
    border: var(--border);
    cursor: pointer;
    font-weight: 800;
    transition: var(--transition);
  }
  
  .load-more:hover {
    background: var(--bg-glass);
    color: var(--text-primary);
    transform: translateY(-2px);
  }

  /* Footer - Enhanced */
  footer {
    margin-top: 80px;
    padding: 60px 20px;
    color: var(--text-muted);
    font-size: 14px;
    text-align: center;
    border-top: var(--border);
  }
  
  a.ghost {
    color: var(--accent-blue);
    font-weight: 800;
    text-decoration: none;
    transition: var(--transition);
  }
  
  a.ghost:hover {
    color: var(--accent-orange);
  }

  /* Focus styles */
  :focus {
    outline: 0;
  }
  
  .focus-ring {
    box-shadow: 0 0 0 3px rgba(54, 163, 235, 0.2);
    border-radius: 8px;
  }

  /* Animations */
  @keyframes fadeIn {
    from { opacity: 0; transform: translateY(10px); }
    to { opacity: 1; transform: translateY(0); }
  }
  
  .card {
    animation: fadeIn 0.5s ease-out;
  }

  /* Responsive adjustments */
  @media (max-width: 880px) {
    .player {
      flex-direction: row;
      gap: 12px;
      padding: 14px;
    }
    
    .prog-bar {
      display: none;
    }
    
    .progress-wrap {
      display: none;
    }
    
    .grid {
      grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
    }
    
    .hero h1 {
      font-size: 32px;
    }
  }
  
  @media (max-width: 680px) {
    header {
      flex-direction: column;
      align-items: flex-start;
      gap: 16px;
    }
    
    .controls {
      flex-direction: column;
      align-items: stretch;
    }
    
    .search {
      width: 100%;
    }
    
    .filters {
      justify-content: center;
    }
    
    .hero h1 {
      font-size: 28px;
    }
    
    .hero p {
      font-size: 16px;
    }
    
    .player {
      flex-wrap: wrap;
      justify-content: center;
    }
    
    .player .info {
      min-width: 100%;
      text-align: center;
      margin-bottom: 8px;
    }
  }
  
  @media (max-width: 480px) {
    .grid {
      grid-template-columns: 1fr;
    }
    
    .hero h1 {
      font-size: 24px;
    }
  }
</style>
</head>
<body class="gradient-bg">

<div class="wrap" id="app">
  <header>
    <div class="brand">
      <div class="logo">BEAT ATLAS</div>
      <div class="tagline">Premium Beats & Packs</div>
    </div>

    <nav aria-label="Main navigation">
      <a href="#beats">Beats</a>
      <a href="#packs">Packs</a>
      <a href="#contact">Contact</a>
    </nav>
  </header>

  <main>
    <section class="hero" aria-labelledby="hero-title">
      <h1 id="hero-title">Dark, tactile beats. Preview fast — buy by email.</h1>
      <p>Edgy, efficient browsing for producers and artists. Click play to audition a 30s preview. Click Buy to email the producer with a prefilled subject.</p>
    </section>

    <!-- controls -->
    <section class="controls" aria-label="Controls">
      <div class="search" role="search" aria-label="Search beats">
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" aria-hidden><path d="M21 21l-4.35-4.35" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/></svg>
        <input id="q" placeholder="Search title, tag, bpm..." aria-label="Search beats" />
      </div>

      <div class="filters" role="toolbar" aria-label="Genre filters" id="filters">
        <!-- chips injected -->
      </div>

      <select id="sort" class="sort-select" aria-label="Sort beats">
        <option value="new">Newest</option>
        <option value="price_asc">Price: Low → High</option>
        <option value="price_desc">Price: High → Low</option>
        <option value="bpm">BPM</option>
      </select>
    </section>

    <!-- beat grid -->
    <section id="beats" aria-live="polite">
      <div class="grid" id="grid" tabindex="-1" aria-label="Beats list">
        <!-- cards injected -->
      </div>

      <button class="load-more" id="loadMore" aria-label="Load more beats">Load more beats</button>
    </section>

    <footer id="contact">
      <p>To purchase, click <strong>Buy</strong> on a beat — it will open your email client with a prefilled subject. Or contact: <a class="ghost" href="mailto:beats@beatatlas.example">beats@beatatlas.example</a></p>
    </footer>
  </main>
</div>

<!-- Sticky player -->
<div class="player" role="region" aria-label="Player" id="player" aria-live="polite">
  <div class="thumb" id="player-thumb" style="background-image:url('');" aria-hidden></div>
  <div class="info">
    <div class="track" id="player-track">No track selected</div>
    <div class="artist" id="player-artist">—</div>
  </div>
  <div class="controls-play" style="align-items:center">
    <button id="btn-prev" class="pv-btn" title="Previous" aria-label="Previous track">⏮</button>
    <button id="btn-play" class="pv-btn" title="Play" aria-label="Play / Pause">▶</button>
    <button id="btn-next" class="pv-btn" title="Next" aria-label="Next track">⏭</button>
  </div>

  <div class="progress-wrap" aria-hidden>
    <div class="prog-bar" role="progressbar" aria-valuemin="0" aria-valuemax="30" aria-valuenow="0" id="prog-bar">
      <div class="prog-fill" id="prog-fill"></div>
    </div>
    <div class="time"><span id="tcur">0:00</span><span id="tmax">0:30</span></div>
  </div>
</div>

<script>
// Data and functionality remain the same as original THINGY
// Only the visual design has been updated

/*
 Data-driven mockup — expand beats[] to simulate hundreds of items.
 Each beat has: id, title, artist, genre, bpm, price, cover (image), type ('beat'|'pack'), tracks (if pack)
*/
const beats = [
  {id:1,title:"Midnight Drive",artist:"ProducerX",genre:"Trap",bpm:90,price:49.99,cover:"https://images.unsplash.com/photo-1470225620780-dba8ba36b745?auto=format&fit=crop&w=800&q=60",type:"beat"},
  {id:2,title:"Urban Dreams",artist:"ProducerX",genre:"Trap",bpm:140,price:59.99,cover:"https://images.unsplash.com/photo-1493225457124-a3eb161ffa5f?auto=format&fit=crop&w=800&q=60",type:"beat"},
  {id:3,title:"Ocean Breeze",artist:"ProducerY",genre:"Pop",bpm:100,price:39.99,cover:"https://images.unsplash.com/photo-1511671782779-c97d3d27a1d4?auto=format&fit=crop&w=800&q=60",type:"beat"},
  {id:4,title:"Dark Alley",artist:"ProducerZ",genre:"Drill",bpm:140,price:69.99,cover:"https://images.unsplash.com/photo-1571330735066-03aaa9429d89?auto=format&fit=crop&w=800&q=60",type:"beat"},
  {id:5,title:"Summer Vibes Pack",artist:"ProducerCollective",genre:"Pack",bpm:null,price:199.99,cover:"https://images.unsplash.com/photo-1519681393784-d120267933ba?auto=format&fit=crop&w=800&q=60",type:"pack",count:10,tracks:["Tropical 1","Tropical 2","Tropical 3"]},
  {id:6,title:"Neon Lights",artist:"SynthLord",genre:"Electronic",bpm:120,price:45.99,cover:"https://images.unsplash.com/photo-1494232410401-ad00d5433cfa?auto=format&fit=crop&w=800&q=60",type:"beat"},
  // add duplicates to simulate more items (for demo load more)
];

for(let i=7;i<=60;i++){
  beats.push({
    id:i,
    title:`Demo Beat ${i}`,
    artist:`Artist ${i%7===0?'A':i%5===0?'B':'C'}`,
    genre:['Trap','Hip-Hop','R&B','Electronic','Pop'][i%5],
    bpm: 80 + (i%80),
    price: 29.99 + (i%6)*5,
    cover:`https://picsum.photos/seed/beat${i}/600/600`,
    type: (i%12===0)?'pack':'beat',
    count: (i%12===0)?(5 + (i%5)): undefined,
    tracks: (i%12===0)?[`Track A${i}`,'Track B','Track C']: undefined
  })
}

/* State & DOM */
const grid = document.getElementById('grid');
const filtersEl = document.getElementById('filters');
const qEl = document.getElementById('q');
const sortEl = document.getElementById('sort');
const loadMoreBtn = document.getElementById('loadMore');

let displayed = 0;
const PAGE = 12;
let activeFilter = 'All';
let query = '';
let sortBy = 'new';

/* player state (fake 30s preview) */
const playerTrack = document.getElementById('player-track');
const playerArtist = document.getElementById('player-artist');
const playerThumb = document.getElementById('player-thumb');
const btnPlay = document.getElementById('btn-play');
const btnPrev = document.getElementById('btn-prev');
const btnNext = document.getElementById('btn-next');
const progFill = document.getElementById('prog-fill');
const progBar = document.getElementById('prog-bar');
const tcur = document.getElementById('tcur');
const tmax = document.getElementById('tmax');

let playlist = []; // array of {id, title, artist, cover, type, tracks}
let currentIndex = -1;
let playing = false;
let progressTimer = null;
let progressSec = 0;
const PREVIEW_LEN = 30;

/* build filters from genre set */
function getGenres(){
  const set = new Set(beats.map(b=>b.genre||'Unknown'));
  return ['All',...Array.from(set).filter(s=>s!=='Pack') , 'Pack'];
}
function renderFilters(){
  const genres = getGenres();
  filtersEl.innerHTML='';
  genres.forEach(g=>{
    const btn = document.createElement('button');
    btn.className='chip'+(g===activeFilter?' active':'');
    btn.textContent=g;
    btn.setAttribute('aria-pressed', g===activeFilter?'true':'false');
    btn.onclick=()=>{ activeFilter=g; displayed=0; document.querySelectorAll('.chip').forEach(c=>c.classList.remove('active')); btn.classList.add('active'); renderGrid(true); }
    filtersEl.appendChild(btn);
  })
}
function matchesFilter(b){
  if(activeFilter==='All') return true;
  if(activeFilter==='Pack') return b.type==='pack';
  return b.genre===activeFilter;
}

/* search+sort utilities */
function searchFilter(b){
  if(!query) return true;
  const q = query.toLowerCase();
  return (b.title && b.title.toLowerCase().includes(q))
      || (b.artist && b.artist.toLowerCase().includes(q))
      || (b.genre && b.genre.toLowerCase().includes(q))
}
function sortBeats(arr){
  if(sortBy==='new') return arr.slice().reverse();
  if(sortBy==='price_asc') return arr.slice().sort((a,b)=> (a.price||0)-(b.price||0));
  if(sortBy==='price_desc') return arr.slice().sort((a,b)=> (b.price||0)-(a.price||0));
  if(sortBy==='bpm') return arr.slice().sort((a,b)=> (a.bpm||0)-(b.bpm||0));
  return arr;
}

/* render grid (incremental) */
function renderGrid(reset=false){
  if(reset) grid.innerHTML='';
  const filtered = beats.filter(b=>matchesFilter(b) && searchFilter(b));
  const sorted = sortBeats(filtered);
  const slice = sorted.slice(displayed, displayed+PAGE);
  slice.forEach(b=>grid.appendChild(makeCard(b)));
  displayed += slice.length;
  loadMoreBtn.style.display = (displayed < sorted.length) ? 'block' : 'none';
}

/* card creation */
function makeCard(b){
  const card = document.createElement('article');
  card.className = 'card';
  card.tabIndex = 0;
  // cover
  const cover = document.createElement('div'); cover.className='cover';
  cover.style.backgroundImage = `url('${b.cover}')`;
  cover.setAttribute('role','img');
  cover.setAttribute('aria-label', `${b.title} cover`);
  // pack badge
  if(b.type==='pack'){
    const badge = document.createElement('div');
    badge.className='pack-badge';
    badge.textContent = `${b.count?b.count+' beats':'PACK'}`;
    cover.appendChild(badge);
  }
  const playWrap = document.createElement('div'); playWrap.className='play';
  const playBtn = document.createElement('button');
  playBtn.innerHTML = '▶';
  playBtn.title = 'Play preview';
  playBtn.onclick = (e)=>{ e.stopPropagation(); queueAndPlay(b); }
  playBtn.onkeyup = (e)=>{ if(e.key==='Enter') queueAndPlay(b); }
  playWrap.appendChild(playBtn);
  cover.appendChild(playWrap);

  // meta
  const meta = document.createElement('div'); meta.className='meta';
  const t = document.createElement('div'); t.className='title'; t.textContent = b.title;
  const sub = document.createElement('div'); sub.className='sub';
  const g = document.createElement('span'); g.className='tag'; g.textContent = b.genre || (b.type==='pack'?'Pack':'—');
  const bpm = document.createElement('span'); bpm.className='tag'; bpm.textContent = b.bpm? b.bpm + ' BPM' : (b.type==='pack' ? `${b.count || 'N'} beats` : '—');
  sub.appendChild(g); sub.appendChild(bpm);

  const price = document.createElement('div'); price.className='price'; price.textContent = (b.price ? `$${b.price.toFixed(2)}`: '—');

  const buy = document.createElement('button'); buy.className='buy';
  buy.innerText = 'Buy / Contact';
  const mailto = `mailto:beats@beatatlas.example?subject=Purchase%20Inquiry%20-%20${encodeURIComponent(b.title)}&body=Hi%20—%20I%20want%20to%20purchase%20"${encodeURIComponent(b.title)}"%20(beat%20id%20${b.id}).%20Please%20send%20licensing%20info.`;
  buy.onclick = ()=> window.location.href = mailto;

  meta.appendChild(t); meta.appendChild(sub); meta.appendChild(price); meta.appendChild(buy);

  // click whole card -> focus/preview
  card.onclick = ()=> queueAndPlay(b);
  card.appendChild(cover);
  card.appendChild(meta);
  return card;
}

/* Player: builds playlist, plays simulated 30s preview */
function buildPlaylistFrom(b){
  // if pack, expand to tracks, else single item
  if(b.type==='pack'){
    const arr = b.tracks && b.tracks.length? b.tracks.map((tr,i)=>({
      id: `${b.id}-t${i}`, title: `${b.title} — ${tr}`, artist: b.artist, cover: b.cover, parentId:b.id
    })): [{id:b.id,title:b.title,artist:b.artist,cover:b.cover}];
    return arr;
  } else {
    return [{id:b.id,title:b.title,artist:b.artist,cover:b.cover}];
  }
}
function queueAndPlay(b){
  playlist = buildPlaylistFrom(b);
  currentIndex = 0;
  startPlayingCurrent();
}

function startPlayingCurrent(){
  if(currentIndex < 0 || currentIndex >= playlist.length) return stopPlayback();
  const item = playlist[currentIndex];
  playerTrack.textContent = item.title;
  playerArtist.textContent = item.artist || '—';
  playerThumb.style.backgroundImage = `url('${item.cover || ''}')`;
  // reset progress and simulate playback
  progressSec = 0;
  setProgress(0);
  playing = true; updatePlayUI();
  // clear existing timer
  if(progressTimer) clearInterval(progressTimer);
  progressTimer = setInterval(()=>{
    progressSec++;
    setProgress(progressSec / PREVIEW_LEN * 100);
    tcur.textContent = formatTime(progressSec);
    progBar.setAttribute('aria-valuenow', Math.min(progressSec,PREVIEW_LEN));
    if(progressSec >= PREVIEW_LEN){
      // auto-advance if there are more tracks in a pack
      if(currentIndex < playlist.length -1){
        currentIndex++;
        startPlayingCurrent();
      } else {
        stopPlayback();
      }
    }
  }, 1000);
}
function stopPlayback(){
  playing = false; updatePlayUI();
  if(progressTimer){ clearInterval(progressTimer); progressTimer=null; }
  progressSec = 0;
  setProgress(0);
  tcur.textContent = formatTime(0);
}
function togglePlayPause(){
  if(!playlist.length) return;
  if(playing){
    // pause
    playing=false;
    if(progressTimer) clearInterval(progressTimer);
  } else {
    // resume
    playing=true;
    progressTimer = setInterval(()=>{
      progressSec++;
      setProgress(progressSec / PREVIEW_LEN * 100);
      tcur.textContent = formatTime(progressSec);
      if(progressSec >= PREVIEW_LEN){
        if(currentIndex < playlist.length -1){
          currentIndex++;
          startPlayingCurrent();
        } else {
          stopPlayback();
        }
      }
    },1000);
  }
  updatePlayUI();
}
function setProgress(percent){
  progFill.style.width = `${Math.max(0,Math.min(100,percent))}%`;
}
function updatePlayUI(){
  if(playing){
    btnPlay.classList.add('playing'); btnPlay.textContent='⏸';
    btnPlay.setAttribute('title','Pause');
  } else {
    btnPlay.classList.remove('playing'); btnPlay.textContent='▶';
    btnPlay.setAttribute('title','Play');
  }
}
function prevTrack(){
  if(currentIndex>0){ currentIndex--; startPlayingCurrent(); }
}
function nextTrack(){
  if(currentIndex < playlist.length-1){ currentIndex++; startPlayingCurrent(); } else { stopPlayback(); }
}

function formatTime(sec){
  sec = Math.max(0, Math.floor(sec));
  const mm = Math.floor(sec/60), ss = sec%60;
  return `${mm}:${ss.toString().padStart(2,'0')}`;
}

/* events */
qEl.addEventListener('input', (e)=>{ query = e.target.value.trim(); displayed=0; renderGrid(true); });
sortEl.addEventListener('change',(e)=>{ sortBy=e.target.value; displayed=0; renderGrid(true); });
loadMoreBtn.addEventListener('click', ()=> renderGrid());

btnPlay.addEventListener('click', togglePlayPause);
btnPrev.addEventListener('click', prevTrack);
btnNext.addEventListener('click', nextTrack);
/* keyboard shortcuts */
document.addEventListener('keydown', (e)=>{
  if(e.code==='Space' && document.activeElement.tagName.toLowerCase()!=='input'){
    e.preventDefault(); togglePlayPause();
  } else if(e.key==='ArrowLeft'){ prevTrack(); }
  else if(e.key==='ArrowRight'){ nextTrack(); }
});

/* init */
renderFilters();
renderGrid();

/* accessibility: focus rings for keyboard users */
document.addEventListener('keydown', (e)=>{
  if(e.key==='Tab') document.body.classList.add('show-focus');
});
document.addEventListener('mousedown', ()=> document.body.classList.remove('show-focus'));

</script>
</body>
</html>

## Key Improvements Inspired by Sunrise Robotics

1. **Modern Color Scheme**:
    
    - Adopted Sunrise's dark background (#0E0E08)
        
    - Used their accent colors (orange #FA6147, blue #36A3EB)
        
    - Improved text contrast with light off-white (#E4E4DD)
        
2. **Enhanced Visual Design**:
    
    - Added gradient backgrounds and text effects
        
    - Improved card design with better hover effects
        
    - Enhanced player with glassmorphism effect
        
    - Added subtle animations and transitions
        
3. **Typography & Layout**:
    
    - Improved font hierarchy and sizing
        
    - Better spacing and alignment throughout
        
    - More professional header with tagline
        
4. **UI Components**:
    
    - Redesigned buttons with gradient accents
        
    - Improved form controls with better focus states
        
    - Enhanced visual feedback on interactions
        

The redesign maintains all the original functionality while giving Beat Atlas a more modern, professional appearance that aligns with the high-tech aesthetic of Sunrise Robotics.