# Demo Video Script & Recording Guide

## 🎥 2-Minute Demo Video Plan

### Objective
Create a concise, impressive demo showcasing your complete real-time streaming platform.

**Target Audience:** Recruiters, hiring managers, technical interviewers  
**Duration:** 2 minutes  
**Format:** Screen recording with voiceover OR text overlays

---

## 🎬 Video Script

### Opening (15 seconds)

**Screen:** Dashboard overview  
**Voiceover:**  
> "Hi, I'm Zaid. This is my real-time cryptocurrency market analyzer—a production-grade streaming data platform I built from scratch for FAANG internship applications. Let me show you how it works."

**Text Overlay:**
```
Real-Time Cryptocurrency Market Analyzer
Built with: Kafka, Flink, Redis, PostgreSQL, FastAPI, Streamlit
```

---

### Architecture (25 seconds)

**Screen:** Show architecture diagram OR README architecture section  
**Voiceover:**  
> "Data flows from CoinGecko API through Apache Kafka to Apache Flink for stream processing. Flink aggregates prices into one, five, and fifteen-minute OHLC windows and detects price anomalies. Results are stored in Redis for sub-10-millisecond cache lookups and PostgreSQL for time-series analysis. FastAPI serves data via REST and WebSocket using Redis Pub/Sub for event-driven updates."

**Text Overlay:**
```
Architecture:
API → Kafka → Flink → Redis/PostgreSQL → FastAPI → Dashboard
```

---

### Live Dashboard (45 seconds)

**Screen 1:** Price cards (10s)  
**Voiceover:**  
> "The dashboard shows live Bitcoin and Ethereum prices updated every two seconds via event-driven WebSocket. Notice the trend indicators and volume display."

**Action:** Point cursor to BTC price card, then ETH

---

**Screen 2:** Candlestick chart (15s)  
**Voiceover:**  
> "I implemented professional OHLC candlestick charts with volume correlation. Green candles indicate price increases, red indicates decreases. The volume bars below show trading activity—notice how they're color-matched to the candles."

**Action:** Hover over candle to show tooltip

---

**Screen 3:** Moving averages (10s)  
**Voiceover:**  
> "For technical analysis, I added twenty and fifty-period moving averages. The blue line is the short-term trend, orange is long-term. When they cross, it signals potential trend changes."

**Action:** Click "Candlestick with MA" to show MA view

---

**Screen 4:** Timeframe selector (10s)  
**Voiceover:**  
> "Users can analyze at multiple timeframes from one hour to twenty-four hours, supporting both short-term and long-term trading strategies."

**Action:** Change timeframe dropdown from "1 Hour" to "4 Hours"

---

### Technical Highlights (25 seconds)

**Screen:** Switch between dashboard views OR show API docs  
**Voiceover:**  
> "Key technical achievements: Sub-ten-millisecond Redis cache hits, sub-hundred-millisecond real-time WebSocket updates via Redis Pub-Sub, exactly-once processing semantics in Flink, and ninety-nine-percent reduction in database operations by switching from polling to event-driven architecture."

**Text Overlay:**
```
Performance Metrics:
• <10ms: Redis cache latency
• <100ms: WebSocket push latency  
• 99%: Reduction in DB operations
• O(1): WebSocket client scalability
```

---

### Closing (10 seconds)

**Screen:** Return to full dashboard  
**Voiceover:**  
> "This project demonstrates real-time stream processing, event-driven architecture, and production-grade engineering patterns. I'd love to discuss any component in detail. Thank you!"

**Text Overlay:**
```
Zaid | Computer Science Student
GitHub: github.com/YOUR_USERNAME/Real-Time-Cryptocurrency-Market-Analyzer
```

---

## 🎬 Recording Setup

### Recording Tools

**Option 1: OBS Studio (Free, Recommended)**
- Download: https://obsproject.com/
- Professional quality
- No watermarks
- Full control over recording settings

**Option 2: Windows Game Bar**
- Built into Windows 10/11
- Press: Win+G
- Quick and easy
- Good quality

**Option 3: ShareX (Free)**
- Powerful screen capture tool
- Video + GIF support
- Easy to use

**Option 4: Loom (Free Tier)**
- Web-based recording
- Easy sharing
- Automatic hosting
- Professional look

---

### Recording Settings

**Resolution:** 1920x1080 (Full HD)  
**Frame Rate:** 30 FPS (smooth enough)  
**Audio:** Optional (voiceover OR text overlays, not both)  
**Duration:** 2 minutes (max 2:30)  
**Format:** MP4 (most compatible)

---

### Pre-Recording Checklist

Before hitting record:

- [ ] Close unnecessary browser tabs
- [ ] Close notification popups
- [ ] Set browser to full screen (F11)
- [ ] Ensure dashboard has fresh data
- [ ] Trigger alert spike beforehand (if showing alerts)
- [ ] Practice run-through once (dry run)
- [ ] Prepare cursor movements (smooth, deliberate)
- [ ] Have script/notes visible on second monitor

---

## 🎙️ Audio Options

### Option A: Voiceover (Recommended)
**Pros:**
- More engaging
- Can explain complex concepts
- Personal touch

**Cons:**
- Requires good microphone
- May need multiple takes
- Harder to edit

**Tips:**
- Use quiet room
- Built-in laptop mic is okay
- Speak clearly and not too fast
- Smile while talking (sounds friendlier!)

---

### Option B: Text Overlays
**Pros:**
- No audio equipment needed
- Easy to edit text
- Works in noisy environments

**Cons:**
- Less engaging
- Viewers must read
- Easy to add too much text

**Tips:**
- Keep text concise (5-7 words per screen)
- Use large, readable font
- High contrast (white text on dark background)
- Display each text for 3-5 seconds

---

### Option C: Silent with Music
**Pros:**
- Professional feel
- No voiceover pressure
- Easy to create

**Cons:**
- Less informative
- Relies on visuals only
- Need copyright-free music

**Tips:**
- Use royalty-free music (YouTube Audio Library)
- Keep volume low (background only)
- Add text annotations for key features

---

## 🎬 Recording Steps

### 1. Preparation (5 minutes)

```powershell
# Ensure everything running
docker-compose ps
START_PRODUCER.bat  # (already running)
START_API.bat       # (already running)
START_DASHBOARD.bat # (already running)

# Trigger alert for demo
python test_spike.py
# Wait 2 minutes

# Refresh dashboard to show alert
```

---

### 2. Recording (10-15 minutes)

1. **Open OBS Studio** (or recording tool)
2. **Select screen** to record (full screen or dashboard window)
3. **Start recording**
4. **Follow script** (see above)
5. **End recording**
6. **Save file**

**Tips:**
- Take 2-3 takes (choose best one)
- Don't worry about perfection
- Smooth cursor movements
- Pause briefly between sections

---

### 3. Editing (10 minutes)

**Basic Edits:**
- Trim start/end (remove setup/teardown)
- Add title card at beginning
- Add text overlays if no voiceover
- Add closing card with contact info

**Tools:**
- **Windows Photos** (basic trimming)
- **DaVinci Resolve** (free, professional)
- **Shotcut** (free, open source)

---

### 4. Export & Upload

**Export Settings:**
- Format: MP4
- Codec: H.264
- Resolution: 1920x1080
- Frame Rate: 30 FPS
- Bitrate: 8-10 Mbps

**Upload To:**
- **YouTube** (unlisted or public)
- **Loom** (easy sharing)
- **Google Drive** (portfolio website embedding)

**Then:**
- Copy video link
- Add to README
- Add to LinkedIn post
- Add to resume (QR code or link)

---

## 🎯 Alternative: Create a GIF

For quick demos (no sound needed):

### Recording a GIF

**Tools:**
- **ScreenToGif** (Windows, free)
- **LICEcap** (cross-platform, free)
- **Gifski** (high quality, free)

**Settings:**
- Duration: 10-15 seconds
- Frame Rate: 15 FPS
- Dimensions: 1280x720 (smaller than video)
- File size: <10MB (GitHub limit)

### GIF Ideas

**GIF 1: Auto-Refresh**
- Show dashboard timestamp updating
- 10 seconds of auto-refresh
- File: `dashboard-autorefresh.gif`

**GIF 2: Chart Interaction**
- Hover over candles, show tooltips
- Zoom in/out
- File: `dashboard-interactive.gif`

**GIF 3: Timeframe Switching**
- Click timeframe selector
- Watch chart update
- File: `dashboard-timeframes.gif`

---

## 📊 Demo Video Checklist

Before considering video complete:

- [ ] Duration: 2-3 minutes
- [ ] Shows all major features
- [ ] Audio clear (if voiceover)
- [ ] Text readable (if overlays)
- [ ] Smooth transitions
- [ ] No awkward pauses
- [ ] Professional opening/closing
- [ ] Contact info visible at end
- [ ] Uploaded and link works
- [ ] Added to README

---

## 🎯 Where to Use Demo Video

**Resume:**
- Add QR code linking to video
- Or short link: bit.ly/zaid-crypto-demo

**LinkedIn:**
- Post as native video
- Or embed YouTube link
- Caption with key tech stack

**Portfolio Website:**
- Embed at top of project page
- YouTube embed code

**GitHub README:**
- Link in "Demo" section
- Markdown: `[📹 Watch Demo Video](https://youtube.com/...)`

**Cold Emails to Recruiters:**
- Include link in first paragraph
- "I'd love to show you a 2-minute demo of my real-time streaming platform"

---

## 🎨 Video Enhancement Ideas

### Professional Touches

**Title Card (3 seconds):**
```
Real-Time Cryptocurrency Market Analyzer
A Production-Grade Streaming Data Platform
By Zaid
```

**Section Markers:**
```
[0:15] Architecture Overview
[0:40] Live Dashboard Demo
[1:25] Technical Highlights
[1:50] Closing
```

**Closing Card (3 seconds):**
```
Zaid
Computer Science Student
GitHub: github.com/YOUR_USERNAME
LinkedIn: linkedin.com/in/YOUR_PROFILE
```

---

## 📈 Success Metrics

Good demo video should:
- [ ] Be under 2:30 (recruiters have limited time)
- [ ] Show working product (not slides/diagrams only)
- [ ] Explain technical value clearly
- [ ] Have professional audio/visuals
- [ ] Include contact information
- [ ] Be shareable (YouTube link)

---

**Status:** Ready to record  
**Next:** Capture screenshots, record video, add to README
