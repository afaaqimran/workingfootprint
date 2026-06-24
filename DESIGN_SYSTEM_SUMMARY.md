# Footprint Design System — Quick Reference

**Status**: Proposal Document (No Implementation Yet)  
**Based On**: datauRepo design patterns  
**Ready For**: Review & Approval

---

## Quick Visual Guide

### Typography

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

HEADING 1: Footprint Analytics
  Font: Inter 600, 24px, -0.5px letter-spacing

HEADING 2: Chart Controls  
  Font: Inter 600, 18px, -0.3px letter-spacing

Body Text: Ready to trade and analyze your positions
  Font: Inter 400, 13px, normal

Label: SYMBOL / TIMEFRAME / DISPLAY
  Font: Inter 500, 11px, 1px letter-spacing (UPPERCASE)

Data/Numbers: 24124.50 | Vol: 1,234,567
  Font: JetBrains Mono 500, 12px, right-aligned

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

### Color Palette

```
PRIMARY BACKGROUND
  #0d1117 (Almost black)
  Used for: Main canvas, body background

SECONDARY BACKGROUND  
  #161b22 (Dark gray-blue)
  Used for: Panels, cards, modals

TERTIARY BACKGROUND
  #21262d (Medium gray-blue)
  Used for: Hover states, buttons

─────────────────────────────────

TEXT COLORS
  Primary:   #e6edf3 (High contrast, headers)
  Secondary: #8b949e (Medium contrast, labels)
  Tertiary:  #6e7681 (Low contrast, hints)

─────────────────────────────────

STATUS COLORS
  Success/Bull:  #26a69a (Teal) [EXISTING]
  Danger/Bear:   #ef5350 (Red) [EXISTING]
  Warning:       #f0ad4e (Orange)
  Info:          #36b9f5 (Blue)
  Accent:        #ffd700 (Gold, for signals)

─────────────────────────────────

INTERACTIVE
  Focus Border:  #58a6ff (Light blue)
  Borders:       #30363d (Medium gray)
  Dividers:      #21262d (Subtle)
```

### Spacing System

```
xs: 4px    (Minimal gaps)
sm: 8px    (Button padding, small gaps)
md: 12px   (Standard padding, control groups)
lg: 16px   (Comfortable spacing, panels)
xl: 24px   (Section gaps)
xxl: 32px  (Major sections)

Example Usage:
┌─────────────────────────────────┐
│  ▌ 12px ▌ Controls ▌ 8px ▌      │  16px (padding)
│  ─────────────────────────────  │
│  [btn] 8px [btn] 12px [input]   │  Gaps between elements
└─────────────────────────────────┘
```

### Component States

```
BUTTON
  Default:   bg: #161b22, text: #e6edf3, border: #30363d
  Hover:     bg: #21262d, text: #e6edf3, border: #58a6ff
  Active:    bg: #26a69a, text: white, border: #26a69a
  Disabled:  opacity: 50%, cursor: not-allowed

INPUT
  Default:   bg: #0d1117, border: #30363d, text: #e6edf3
  Focus:     border: #58a6ff, shadow: rgba(88, 166, 255, 0.1)
  Error:     border: #ef5350, text: #ef5350
  Success:   border: #26a69a

TABS
  Inactive:  text: #8b949e, bg: transparent
  Active:    text: #26a69a, border-left: 3px #26a69a, bg: rgba(38, 166, 154, 0.05)
  Hover:     text: #e6edf3, bg: #21262d
```

---

## Implementation Quick Start

### Step 1: Google Fonts

```html
<head>
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600&family=JetBrains+Mono:wght@400;500;600&display=swap" rel="stylesheet">
</head>
```

### Step 2: CSS Variables

```css
:root {
  /* Fonts */
  --font-inter: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
  --font-mono: 'JetBrains Mono', 'Courier New', monospace;
  
  /* Colors - Background */
  --color-bg-primary: #0d1117;
  --color-bg-secondary: #161b22;
  --color-bg-tertiary: #21262d;
  
  /* Colors - Text */
  --color-text-primary: #e6edf3;
  --color-text-secondary: #8b949e;
  --color-text-tertiary: #6e7681;
  
  /* Colors - Status */
  --color-success: #26a69a;
  --color-danger: #ef5350;
  --color-warning: #f0ad4e;
  --color-info: #36b9f5;
  --color-accent: #26a69a;
  
  /* Colors - UI */
  --color-border: #30363d;
  --color-focus: #58a6ff;
  
  /* Spacing */
  --spacing-xs: 4px;
  --spacing-sm: 8px;
  --spacing-md: 12px;
  --spacing-lg: 16px;
  --spacing-xl: 24px;
  --spacing-xxl: 32px;
}
```

### Step 3: Apply Base Styles

```css
* {
  font-family: var(--font-inter);
  box-sizing: border-box;
}

body {
  background: var(--color-bg-primary);
  color: var(--color-text-primary);
  line-height: 1.5;
}

/* Headings */
h1, h2, h3 { font-weight: 600; letter-spacing: -0.5px; }
h1 { font-size: 24px; }
h2 { font-size: 18px; }

/* Labels & Small Text */
label, .label { 
  font-size: 11px; 
  font-weight: 600; 
  text-transform: uppercase; 
  letter-spacing: 1px; 
  color: var(--color-text-secondary);
}

/* Data/Numeric */
.data, .numeric { 
  font-family: var(--font-mono); 
  font-weight: 500; 
  text-align: right;
}
```

### Step 4: Update Components

```css
/* Buttons */
.btn {
  background: var(--color-bg-secondary);
  color: var(--color-text-primary);
  border: 1px solid var(--color-border);
  border-radius: 6px;
  padding: 8px 12px;
  font-size: 12px;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.2s ease;
}

.btn:hover {
  background: var(--color-bg-tertiary);
  border-color: var(--color-focus);
}

.btn.active {
  background: var(--color-accent);
  color: white;
  border-color: var(--color-accent);
}

/* Inputs */
.input {
  background: var(--color-bg-secondary);
  color: var(--color-text-primary);
  border: 1px solid var(--color-border);
  border-radius: 6px;
  padding: 10px 12px;
  font-family: var(--font-inter);
  font-size: 12px;
}

.input:focus {
  outline: none;
  border-color: var(--color-focus);
  box-shadow: 0 0 0 3px rgba(88, 166, 255, 0.1);
}
```

---

## Before & After Comparison

### Login Page

**BEFORE**: 
- Generic system fonts
- Limited visual hierarchy
- Basic colors
- Minimal spacing definition

**AFTER**:
- Professional typography (Inter 600 for headers)
- Clear visual hierarchy (multiple font weights)
- Expanded color palette with better contrast
- Refined spacing (16px padding, 8px gaps)
- Modern focus states and transitions

### Controls Panel

**BEFORE**:
```
[Symbol ▼] [1m] [5m] [15m] [Footprint] [Candles] [Settings] [Logout]
(Single row, cramped, no grouping)
```

**AFTER**:
```
╔═══════════════════════════════════════════════════════════╗
│ Symbol         Timeframe           Display        Settings │
│ [NIFTY ▼]  [1m] [5m] [15m] ▢  [Footprint] [Candles] [⚙️]  │
│                                              (Logout)  [×] │
╚═══════════════════════════════════════════════════════════╝
(Grouped, labeled, hierarchical)
```

### Data Display

**BEFORE**:
```
Price: 24124.50
Volume: 1234567
```

**AFTER**:
```
PRICE (Inter 500 11px uppercase label)
24124.50 (JetBrains Mono 500 12px, right-aligned, high contrast)

VOLUME (same label style)
1,234,567 (same data style with thousands separator)
```

---

## File Changes Summary

### Files to Create
- `templates/css/design-system.css` - Core variables and base styles
- `templates/css/components.css` - Component-specific styling

### Files to Update
- `templates/chart.html` - Add font links, update inline styles
- `templates/login_upstox.html` - Update login page styling
- Any other HTML files with inline styles

### No Files to Delete
- All existing functionality preserved
- Pure CSS improvements
- No structure changes needed

---

## Migration Checklist

- [ ] Review proposal and approve changes
- [ ] Create CSS variable file
- [ ] Add Google Fonts import
- [ ] Update button styling
- [ ] Update input styling
- [ ] Update colors globally
- [ ] Update login page design
- [ ] Update sidebar navigation
- [ ] Update data rendering fonts
- [ ] Test across browsers
- [ ] Verify accessibility
- [ ] Deploy and monitor

---

## Performance Impact

**Download Size**: +75KB (one-time, heavily cached)
- Fonts: ~60KB gzipped
- CSS: ~15KB gzipped

**Rendering**: No negative impact
- CSS variables are browser-cached
- No JavaScript-heavy styling
- Fonts use `font-display: swap` for fast rendering

**Result**: Imperceptible to user, major visual improvement

---

## Next Steps

1. **Review**: Please review this proposal
2. **Approve**: Confirm fonts, colors, and layout preferences
3. **Clarify**: Answer the 6 questions in proposal document
4. **Implement**: Start with Phase 1 (Foundation)
5. **Test**: Verify across devices and browsers
6. **Deploy**: Roll out to production

---

## Key Files for Reference

- Full Proposal: `LAYOUT_FONTS_PROPOSAL.md`
- Design System Summary: This file
- Fonts Used:
  - Google Fonts: `Inter` (primary), `JetBrains Mono` (data)
  - Reference: datauRepo design patterns

---

## Questions?

This proposal provides:
- ✅ Complete typography system
- ✅ Comprehensive color palette
- ✅ Spacing & layout guidelines  
- ✅ Component styling templates
- ✅ Implementation phases
- ✅ Browser compatibility info
- ✅ Accessibility considerations
- ✅ Performance analysis

**Ready to implement when you give the green light!**
