# Day 55 — Cross-Browser & Mobile Verification

## Desktop Browsers

### Chrome / Edge (Chromium-based)
- [ ] `/` renders hero + feature cards + how-it-works
- [ ] `/chat` loads sidebar + chat window
- [ ] Send message → SSE tokens stream progressively
- [ ] Tax breakdown card renders; lazy chunk fetch visible in Network
- [ ] Theme toggle works (light/dark mode)
- [ ] Focus rings visible on Tab; Enter submits in MessageInput
- [ ] No console errors or hydration warnings

### Firefox
- [ ] `/` renders all sections with correct layout
- [ ] `/chat` chat window functional
- [ ] SSE streaming works (Firefox handles text/event-stream correctly)
- [ ] Cards render correctly
- [ ] Dark mode toggle functional
- [ ] Keyboard navigation works

### Safari (macOS)
- [ ] `/` loads and renders (particularly important for older Safari versions)
- [ ] `/chat` SSE streaming works (Safari sometimes has issues with text/event-stream)
- [ ] Cards render and update correctly
- [ ] Theme toggle works
- [ ] No layout shifts or rendering artifacts

## Mobile Testing

### iOS Safari (375px viewport)
- [ ] Touch targets ≥ 44×44px
- [ ] Safe-area insets respected (notch handling)
- [ ] No horizontal scroll at 375px
- [ ] Keyboard doesn't obscure MessageInput
- [ ] OS dark-mode propagates
- [ ] Sidebar drawer opens/closes correctly

### Android Chrome (360px viewport)
- [ ] Touch targets ≥ 44px
- [ ] Responsive layout adjusts correctly
- [ ] No horizontal scroll
- [ ] Keyboard handling works
- [ ] System dark mode respected
- [ ] Pinch zoom functional

## Results Summary

### Device Testing Completed
- [ ] Real device testing (iOS / Android): [date or pending]
- [ ] DevTools device emulation: [date or pending]

### Issues Found & Fixed
(Record any CSS/layout issues encountered and how they were resolved)

---

**Status:** Pending manual verification after `npm run dev` is running
