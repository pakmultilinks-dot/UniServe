# UniServe Mobile — UX/UI Redesign Specification

**Version:** 1.0  
**Date:** 2026-09-28  
**Status:** Design Discovery & Specification (no code changes)  
**Baseline Commit:** `27b253f`

---

## Table of Contents

1. [Current UI Teardown](#1-current-ui-teardown)
2. [Problems with Current UX](#2-problems-with-current-ux)
3. [Reference Patterns Researched](#3-reference-patterns-researched)
4. [LGU Branding Findings](#4-lgu-branding-findings)
5. [New Information Architecture](#5-new-information-architecture)
6. [Home Screen Specification](#6-home-screen-specification)
7. [Menu & Card Specification](#7-menu--card-specification)
8. [Item Detail Specification](#8-item-detail-specification)
9. [Cart Specification](#9-cart-specification)
10. [Navigation Specification](#10-navigation-specification)
11. [Color System](#11-color-system)
12. [Typography](#12-typography)
13. [Motion Principles](#13-motion-principles)
14. [Empty / Error / Loading States](#14-empty--error--loading-states)
15. [Dark Mode](#15-dark-mode)
16. [Mobile Usability Principles](#16-mobile-usability-principles)
17. [Implementation Slices](#17-implementation-slices)
18. [Non-Goals](#18-non-goals)

---

## 1. Current UI Teardown

### 1.1 Screen Inventory

| Screen | File | Lines | Primary Function |
|---|---|---|---|
| Login | `app/(auth)/login.tsx` | ~135 | Email/password auth |
| Register | `app/(auth)/register.tsx` | ~175 | New account creation |
| Home | `app/(tabs)/index.tsx` | ~800 | Menu browsing, cafeteria selection, search |
| Orders | `app/(tabs)/orders.tsx` | ~115 | Order history list |
| Profile | `app/(tabs)/profile.tsx` | ~145 | User info, logout |
| Cart | `app/cart.tsx` | ~275 | Cart items, quantities, checkout placeholder |
| Item Detail | `app/item/[id].tsx` | ~290 | Single item view, add to cart |

### 1.2 Component Library

| Component | File | Purpose |
|---|---|---|
| Button | `src/components/ui/Button.tsx` | 5 variants, 3 sizes |
| Card | `src/components/ui/Card.tsx` | White card with border (not theme-aware) |
| LguInput | `src/components/ui/Input.tsx` | Text input with label |
| PasswordInput | `src/components/ui/Input.tsx` | Password with emoji toggle |
| Spinner | `src/components/ui/Spinner.tsx` | ActivityIndicator + label |
| EmptyState | `src/components/ui/EmptyState.tsx` | Emoji + title + description |
| StatusChip | `src/components/ui/StatusChip.tsx` | Colored status badges |
| LguSeal | `src/components/LguSeal.tsx` | Shield-shaped logo (pure RN, no SVG) |

### 1.3 Navigation Structure (Current)

```
Root Stack
├── (auth) Stack
│   ├── login
│   └── register
└── (app) Stack
    ├── (tabs) Bottom Tabs
    │   ├── index (Home)       — icon: 🏠
    │   ├── orders (Orders)    — icon: 📋
    │   └── profile (Profile)  — icon: 👤
    ├── cart                    — pushed screen
    └── item/[id]              — pushed screen
```

### 1.4 Emoji Inventory (All Screen Elements)

The current UI uses emojis as **every icon and visual element**:

| Context | Emoji | Count of Uses |
|---|---|---|
| Tab icons | 🏠 📋 👤 | 3 |
| Notification bell | 🔔 | 1 |
| Cafeteria indicator | 🍽️ | 2 |
| Food category icons | 🍳 🍛 🥗 🍰 ☕ 🍿 🥬 🍜 | 8 |
| Search icon | 🔍 | 1 |
| Menu item thumbnails | 🍳 🍛 🥗 🍰 ☕ 🍿 🥬 🍜 🍽️ | 9 (same as categories) |
| Cart empty | 🛒 | 1 |
| Checkout placeholder | 💳 | 1 |
| Item error | 😵 | 1 |
| Error boxes | ⚠️ | 2 |
| Allergens label | ⚠️ | 1 |
| Dietary label | 🥗 | 1 |
| Password toggle | 🙈 👁️ | 2 |
| Verified check | ✓ | 1 |
| Cart bar arrow | → | 1 |
| Back link | ← | 1 |
| Search clear | ✕ | 1 |

**Total: 24+ distinct emoji usages across the app.** No vector icons, no image assets, no SVG icons.

### 1.5 Color Usage (Current)

- **Primary brand:** `#005400` (brand[700]) — used for: buttons, active tabs, price text, cart bar, avatar background, category chip active state, role badge
- **Gold:** `#ffc000` (gold[500]) — used for: LGU seal bar only
- **Backgrounds:** `#ffffff` (primary), `#f2f3f5` (secondary), `#e5e7eb` (tertiary)
- **Text:** `#111827` (primary), `#4a4e57` (secondary), `#6b7280` (muted)
- **Borders:** `#e5e7eb` (default), `#f3f4f6` (subtle)
- **Hardcoded error colors:** `#fef2f2`, `#fecaca`, `#991b1b` (not theme-aware)
- **Hardcoded warning colors:** `#fff7ed`, `#fed7aa`, `#9a3412` (not theme-aware)

### 1.6 Typography (Current)

| Element | Size | Weight | Line Height |
|---|---|---|---|
| Screen greeting | 22px | 700 | 28 |
| Section title | 13px | 600 | — |
| Item name (card) | 15px | 600 | 20 |
| Item name (detail) | 24px | 700 | 32 |
| Price | 15px | 700 | — |
| Description | 12-14px | 400 | 18-20 |
| Body | 16px | 400 | 24 |
| Caption | 12px | 400 | 16 |
| Button | 15-16px | 600 | 24 |

---

## 2. Problems with Current UX

### 2.1 Structural Problems

| Problem | Severity | Details |
|---|---|---|
| **Emoji-only icons** | Critical | 24+ emoji usages replace all icons. No vector icons. Emoji rendering varies across devices (iOS/Android/Web look different). Looks like a prototype. |
| **No food imagery** | Critical | Menu items display emoji category icons (80×80px) instead of food photos. A cafeteria ordering app without food photography is visually unconvincing. |
| **Dashboard architecture** | High | 800-line Home screen serves as menu browser + cafeteria selector + search + cart — a kitchen-sink screen rather than a focused food discovery experience. |
| **No persistent cart visibility** | High | Cart is a separate pushed screen. Users must navigate away from browsing to check cart state. Only the floating bar provides minimal cart awareness. |
| **Generic card patterns** | High | All screens use identical white cards with 1px borders. No visual hierarchy between primary content and supporting information. |
| **No image support in cards** | High | MenuItemCard is a horizontal row: emoji (80×80) + text. No grid layout, no image ratio, no visual food representation. |
| **Fixed bottom tabs** | Medium | Only 3 tabs (Home, Orders, Profile). No Favorites, no quick cart access via tab. |
| **"33 cafeterias" pattern** | Medium | The greeting says "What would you like today?" which is good, but the cafeteria badge is a small secondary element rather than a confident location anchor. |
| **Checkout is a placeholder** | Medium | "💳 Checkout and payment will be available in the next update." — dashed border, no CTA. |
| **No skeleton loading** | Medium | All loading states use full-screen Spinners. No progressive loading or skeleton screens. |
| **Theme not fully wired** | Medium | ThemeContext exists but no toggle UI. Error/warning colors are hardcoded and not theme-aware. |
| **Card component not theme-aware** | Medium | Card always renders white background regardless of theme. Dark mode would break. |

### 2.2 Visual Problems

| Problem | Details |
|---|---|
| **Emoji as food thumbnails** | 🍛 as a "food photo" is visually meaningless. Users cannot scan items visually. |
| **No visual hierarchy** | Every card looks the same. No featured items, no promoted items, no visual weight differences. |
| **Color overuse** | `#005400` appears on buttons, tabs, prices, avatars, badges, chips — everything is the same green. No visual differentiation. |
| **Flat spacing** | Uniform 10-12px gaps everywhere. No breathing room between major sections. |
| **Inconsistent padding** | Screen padding ranges from 12px to 24px with no clear rhythm. |
| **Tiny category chips** | 13px uppercase section labels + pill chips feel small and cramped. |
| **Notification bell as emoji** | 🔔 renders differently on every platform. Should be a vector icon. |
| **Password toggle as emoji** | 🙈/👁️ toggles look amateurish. |
| **Header inconsistency** | Login has centered layout. Home has split header. Cart has no header. Item detail has no back button visible in the content area. |

### 2.3 UX Flow Problems

| Problem | Details |
|---|---|
| **No add-to-cart feedback** | Tapping "+" on a menu card adds the item silently. No toast, no animation, no confirmation. |
| **Cart bar is the only cart access** | Users cannot see cart contents without leaving the menu. The floating bar shows count + total but not what's in it. |
| **Item detail image area is wasted** | 220px tall area shows a single emoji. That space should show a food photo. |
| **No quantity on menu cards** | Users cannot see how many of each item are in their cart from the menu view. |
| **Orders screen is minimal** | Just order number, status chip, total, date. No item preview, no reorder button, no pickup details. |
| **Profile screen is purely informational** | Shows user data + logout. No settings, no preferences, no order preferences. |
| **No pull-to-refresh indication** | Home screen has no refresh control. |

---

## 3. Reference Patterns Researched

### 3.1 Industry Benchmarks

| App | Key Pattern | Applicability |
|---|---|---|
| **UberEats** | Food-first grid, black UI chrome, green CTAs, persistent cart bar | High — clean separation of food vs chrome |
| **DoorDash** | Category tabs + food grid, red CTAs, card-based menu, skeleton loading | High — card layout, skeleton patterns |
| **Foodpanda** | Pink brand, horizontal category scroll, quick-add buttons, order tracking | Medium — cart UX, order tracking |
| **Zomato** | Food photography dominant, quantity badges on cards, restaurant-as-header | High — card quantity controls, restaurant header |
| **Grubhub** | Restaurant cards, menu sections, reorder from history | Medium — reorder pattern |
| **MealPe (Campus)** | Campus-specific ordering, pickup scheduling, meal plans | Medium — campus-specific patterns |
| **Starbucks Mobile** | Customization flow, mobile order + pickup, rewards integration | Low — too complex for UniServe's scope |

### 3.2 Patterns Adopted for UniServe

| Pattern | Source | Rationale |
|---|---|---|
| **Food-first home screen** | UberEats, DoorDash | The home screen IS the menu. No dashboard layer. |
| **Compact food cards in grid** | DoorDash, Zomato | 2-column grid allows scanning 4+ items at once. |
| **Quantity badge on card "+" button** | Zomato, Foodpanda | Users see cart state without leaving the menu. |
| **Floating cart bar (persistent)** | UberEats, DoorDash | Always visible, always tappable, shows count + total. |
| **Category horizontal scroll** | All major apps | Compact, familiar, space-efficient. |
| **Skeleton loading** | DoorDash | Perceived performance improvement over spinner. |
| **"Added to cart" toast** | All major apps | Essential feedback loop. |
| **Restaurant/cafeteria as top context** | UberEats | Cafeteria name + status always visible as anchor. |
| **Reorder from history** | Grubhub, UberEats | High-frequency campus use case. |
| **Swipe-to-delete in cart** | UberEats, DoorDash | Standard mobile cart pattern. |

---

## 4. LGU Branding Findings

### 4.1 Official Color Palette

| Token | Hex | Role | Usage Ratio |
|---|---|---|---|
| **Primary Green** | `#005400` | Brand identity, CTAs | 10-15% of screen area |
| **Gold Accent** | `#ffc000` | Highlights, badges, specials | 3-5% of screen area |
| **Navy** | `#212934` | Dark mode backgrounds, headers | Dark mode only |
| **Charcoal** | `#4a4e57` | Secondary text | Supporting |
| **Surface** | `#f2f3f5` | Light backgrounds | 30-40% |
| **White** | `#ffffff` | Cards, primary background | 40-50% |

### 4.2 Logo / Seal

- **Shape:** Shield/crest (pointed bottom, wider top)
- **Colors:** Green `#005400` background, gold `#ffc000` bar, white book icon, gold "LGU" text
- **Sizes:** 80px (login), 60px (register), 40px (profile footer)
- **Construction:** Pure React Native shapes (no SVG) — sufficient for current use

### 4.3 Brand Direction

**Key insight:** The brand green is very dark (`#005400`). This is an institutional military green, not a bright app green. Using it as the sole accent across all UI elements creates a heavy, monotonous appearance.

**Recommended approach:**
- LGU green appears in: the logo/seal, the primary CTA button, the bottom tab active state
- LGU gold appears in: "Today's Special" badges, premium item indicators, the seal bar
- The food imagery IS the color — food photos provide warmth, variety, and appetite appeal
- Neutral backgrounds (white, light gray) let food photos be the visual hero
- LGU identity is **restrained and consistent**, not dominant

**The app should feel like a modern food ordering app that happens to be LGU's — not an LGU website that happens to sell food.**

---

## 5. New Information Architecture

### 5.1 Recommended Navigation

```
Bottom Tab Bar (4 tabs)
├── 🏠 Home           — Food discovery + cafeteria context
├── 📋 My Orders      — Order history + reorder
├── ❤️ Favorites       — Saved items (future) / placeholder
└── 👤 Profile        — Account + settings

Persistent Elements
├── Cart Bar           — Floating, appears when cart has items
├── Cart Screen        — Pushed from cart bar tap
└── Item Detail        — Pushed from food card tap
```

### 5.2 Rationale

**Why 4 tabs:**
- Home: The primary action — browse and order food
- My Orders: Second most common action — check order status, reorder
- Favorites: Placeholder for future — students have "usual orders" they want to save
- Profile: Account management, settings, logout

**Why NOT a Cafeterias tab:**
- UniServe currently has a single cafeteria per deployment context
- Cafeteria selection belongs on the Home screen as context, not a separate tab
- If multi-cafeteria support grows, it becomes a modal/sheet from Home, not a permanent tab

**Why Cart is NOT a tab:**
- Cart is a temporary state, not a permanent destination
- The floating cart bar provides constant visibility
- Tapping the bar pushes the full cart screen
- This follows UberEats/DoorDash/Foodpanda convention

**Why Favorites is included (even as placeholder):**
- Students reorder the same items daily — "Favorites" is the natural home for this
- Even an empty placeholder communicates that the feature is coming
- Prevents a 3-tab layout that feels sparse

### 5.3 Customer Journey Flow

```
Login
  → Home (food browsing, cafeteria context)
    → Item Detail (tap food card)
      → Add to Cart (quantity + "Add to Cart" button)
        → Cart Bar updates (count + total appears/updates)
          → Cart Screen (tap cart bar)
            → Checkout (future slice)
              → Order Confirmation
                → Orders tab (track status)
                  → Pickup

  OR from Orders tab:
    → Reorder (tap "Order Again" on past order)
      → Cart populated with same items
        → Cart → Checkout → Order → Pickup
```

### 5.4 Screen Map

| Screen | Access | Function |
|---|---|---|
| Login | Root (unauthenticated) | Email/password authentication |
| Register | From Login | New account creation |
| Home | Bottom tab 1 | Cafeteria context + category browsing + food grid + search |
| Item Detail | Push from Home food card | Large image + details + add to cart |
| Cart | Push from Cart Bar | Item list + quantities + totals + proceed |
| My Orders | Bottom tab 2 | Order history + status + reorder |
| Favorites | Bottom tab 3 | Saved items (empty state initially) |
| Profile | Bottom tab 4 | Account info + settings + logout |

---

## 6. Home Screen Specification

### 6.1 Screen Zones

```
┌─────────────────────────────────────┐
│  ZONE 1: Status Bar (system)        │
├─────────────────────────────────────┤
│  ZONE 2: Header                     │
│  ┌─────────────────────────────────┐│
│  │ Good morning, Test    [🔔] [👤] ││
│  │ Auto C1 · Building A  ● Open    ││
│  └─────────────────────────────────┘│
├─────────────────────────────────────┤
│  ZONE 3: Search                     │
│  ┌─────────────────────────────────┐│
│  │ 🔍 Search menu items...         ││
│  └─────────────────────────────────┘│
├─────────────────────────────────────┤
│  ZONE 4: Categories                 │
│  [All] [🍛 Main] [🍳 Breakfast]    │
│  [🥗 Side] [🍰 Dessert] [☕ Bev]  │
├─────────────────────────────────────┤
│  ZONE 5: Food Grid (scrollable)     │
│  ┌──────────┐  ┌──────────┐        │
│  │  [image] │  │  [image] │        │
│  │  Name    │  │  Name    │        │
│  │  PKR 150 │  │  PKR 200 │        │
│  │  [+ 2]   │  │  [+]     │        │
│  └──────────┘  └──────────┘        │
│  ┌──────────┐  ┌──────────┐        │
│  │  ...     │  │  ...     │        │
│  └──────────┘  └──────────┘        │
├─────────────────────────────────────┤
│  ZONE 6: Floating Cart Bar          │
│  ┌─────────────────────────────────┐│
│  │ 🛒 2 items        PKR 350  →   ││
│  └─────────────────────────────────┘│
├─────────────────────────────────────┤
│  Bottom Tab Bar                     │
│  [Home] [Orders] [Favorites] [Me]  │
└─────────────────────────────────────┘
```

### 6.2 Zone Details

#### ZONE 2: Header

```
┌─────────────────────────────────────┐
│ Good morning, Test          [🔔]   │
│ Auto C1 · Building A  ● Open       │
└─────────────────────────────────────┘
```

| Element | Specification |
|---|---|
| Greeting | "Good morning/afternoon/evening, {firstName}" — 24px, 700, letterSpacing -0.5, textPrimary |
| Notification icon | 24×24 vector icon (Bell), 40×40 touch target, circle bg (bgSecondary) |
| Cafeteria name | "{cafeteria.name}" — 16px, 600, textPrimary |
| Location | "· {cafeteria.location}" — 14px, 400, textMuted |
| Status dot | 8×8 circle — green (success) when open, amber (warning) closing soon, red (error) closed |
| Status text | "Open" / "Closing soon" / "Closed" — 12px, 500, matches dot color |

**Layout:** `paddingHorizontal: 20`, `paddingTop: 12`, `paddingBottom: 8`  
**Spacing:** Greeting row → 6px gap → Cafeteria row

**Behavior:**
- Tapping cafeteria name opens a bottom sheet with cafeteria details (hours, location, description)
- Notification icon navigates to notifications (future slice)
- When no cafeteria is available: Show "No cafeteria available" with a muted icon

#### ZONE 3: Search

```
┌─────────────────────────────────────┐
│ 🔍 Search menu items...        [✕] │
└─────────────────────────────────────┘
```

| Element | Specification |
|---|---|
| Container | `height: 44`, `borderRadius: 12`, `bg: bgSecondary`, `borderWidth: 0` (no border, bg color provides contrast) |
| Search icon | 18×18, textMuted, left padding 14 |
| TextInput | fontSize 15, placeholder textMuted, flex 1 |
| Clear button | 18×18, textMuted, right padding 14 (shown when text present) |

**Behavior:**
- Search is instant (no submit button) — filters as user types
- Clear button clears text and returns to full menu
- When searching, show result count: "{N} items found" (12px, textMuted)

#### ZONE 4: Categories

```
[All] [🍛 Main Course] [🍳 Breakfast] [🥗 Side] [🍰 Dessert] [☕ Beverage] →
```

| Element | Specification |
|---|---|
| Container | Horizontal `ScrollView`, `paddingHorizontal: 20`, `gap: 8`, shows horizontal scroll indicator |
| Chip (inactive) | `paddingHorizontal: 14`, `paddingVertical: 8`, `borderRadius: 20`, bg: bgSecondary, text: textSecondary, fontSize: 13, fontWeight: 500 |
| Chip (active) | Same dimensions, bg: brandGreen, text: white |
| "All" chip | Always first. Active when no category filter. |
| Category emoji | 14px, precedes text label |

**Behavior:**
- Horizontal scroll with fade indicator on right edge when more categories available
- Tap selects category, deselects previous
- "All" shows all items
- Smooth scroll to keep active chip visible

#### ZONE 5: Food Grid

```
┌─────────────────┐  ┌─────────────────┐
│  ┌────────────┐ │  │  ┌────────────┐ │
│  │   [Food    │ │  │  │   [Food    │ │
│  │    Photo]  │ │  │  │    Photo]  │ │
│  │            │ │  │  │            │ │
│  └────────────┘ │  │  └────────────┘ │
│  Butter Chicken │  │  Chicken Biryani│
│  Rich creamy... │  │  Fragrant rice..│
│  PKR 250    [+]│  │  PKR 180    [+] │
└─────────────────┘  └─────────────────┘
```

**Grid layout:**
| Property | Value |
|---|---|
| Columns | 2 |
| Gap | 12px |
| Padding | `paddingHorizontal: 20` |
| Scroll | Vertical `FlatList` or `ScrollView` with `contentContainerStyle: { paddingBottom: 100 }` (space for cart bar + tab bar) |

**Behavior:**
- Pull-to-refresh supported
- When searching, switches to single-column list view for better readability
- Scroll-to-top when tapping the active category tab

---

## 7. Menu & Card Specification

### 7.1 Food Card (Grid View)

```
┌───────────────────────┐
│  ┌───────────────────┐│
│  │                   ││
│  │    [Food Image]   ││
│  │    1:1 ratio      ││
│  │                   ││
│  │              [2]  ││  ← quantity badge (only when in cart)
│  └───────────────────┘│
│  Butter Chicken       │
│  Rich creamy curry... │
│  PKR 250         [+] │
└───────────────────────┘
```

| Property | Specification |
|---|---|
| Container | `borderRadius: 12`, `bg: bgPrimary`, `overflow: "hidden"` |
| Image | `aspectRatio: 1` (square), `width: "100%"`, `resizeMode: "cover"` |
| Image placeholder | When no image: solid `bgSecondary` with centered category emoji (32px) |
| Quantity badge | When item in cart: absolute positioned top-right of image, `bg: brandGreen`, white text (12px/700), `borderRadius: 10`, `paddingHorizontal: 8`, `paddingVertical: 2` |
| Content padding | `padding: 10` below image |
| Name | 14px, 600, textPrimary, `numberOfLines: 1`, `ellipsizeMode: "tail"` |
| Description | 12px, 400, textMuted, `numberOfLines: 1`, `marginTop: 2` |
| Price row | `flexDirection: "row"`, `justifyContent: "space-between"`, `alignItems: "center"`, `marginTop: 6` |
| Price | 15px, 700, brandGreen |
| Add button | When not in cart: 28×28 circle, bg: brandGreen, white "+" icon (14px) |
| Add button (with qty) | When in cart: compact `[- 2 +]` stepper, 28×28 buttons, bg: bgSecondary, borderRadius: 8 |

**Card dimensions (estimated on iPhone 14):**
- Image: ~170×170px
- Content: ~60px
- Total card height: ~230px
- Two cards per row with 12px gap = ~170px each

### 7.2 Food Card (List View — Search Results)

```
┌─────────────────────────────────────────────────┐
│  ┌────────────┐  Butter Chicken                 │
│  │            │  Rich creamy curry with tender   │
│  │  [Image]   │  chicken pieces...               │
│  │  1:1       │  PKR 250                    [+] │
│  └────────────┘                                  │
└─────────────────────────────────────────────────┘
```

| Property | Specification |
|---|---|
| Container | `flexDirection: "row"`, `padding: 12`, `borderRadius: 12`, `bg: bgPrimary` |
| Image | 72×72, `borderRadius: 8`, `resizeMode: "cover"` |
| Image placeholder | 72×72, bgSecondary, centered category emoji (24px) |
| Content | `flex: 1`, `marginLeft: 12` |
| Name | 15px, 600, textPrimary, `numberOfLines: 1` |
| Description | 13px, 400, textMuted, `numberOfLines: 1` |
| Price | 14px, 700, brandGreen |
| Add button | Same as grid card |

### 7.3 "Today's Special" Card (Optional Hero)

```
┌───────────────────────────────────────────┐
│  ⭐ Today's Special                       │
│  ┌─────────────────────────────────────┐  │
│  │                                     │  │
│  │         [Large Food Photo]          │  │
│  │            16:9 ratio               │  │
│  │                                     │  │
│  └─────────────────────────────────────┘  │
│  Butter Chicken Biryani          PKR 250  │
│  Chef's special with saffron rice   [+]   │
└───────────────────────────────────────────┘
```

| Property | Specification |
|---|---|
| Container | `borderRadius: 12`, `bg: bgPrimary`, full width |
| Badge | "⭐ Today's Special" — `bg: gold[500]`, text: neutral[900], 12px/700, paddingHorizontal: 10, paddingVertical: 4, borderRadius: 6, position: absolute top-left |
| Image | `aspectRatio: 16/9`, `width: "100%"`, `resizeMode: "cover"` |
| Content | paddingHorizontal: 14, paddingVertical: 10 |
| Name | 16px, 700, textPrimary |
| Price | 16px, 700, brandGreen, right-aligned |
| Description | 13px, 400, textMuted, numberOfLines: 1 |

**Note:** "Today's Special" is a future enhancement. The backend does not currently have a `featured` or `special` flag on menu items. This card is defined here for design completeness but should NOT be implemented until the backend supports it.

---

## 8. Item Detail Specification

### 8.1 Screen Layout

```
┌─────────────────────────────────────┐
│  ← Back                             │
├─────────────────────────────────────┤
│  ┌─────────────────────────────────┐│
│  │                                 ││
│  │         [Food Image]            ││
│  │         Full width              ││
│  │         3:2 ratio               ││
│  │                                 ││
│  └─────────────────────────────────┘│
├─────────────────────────────────────┤
│                                     │
│  [Main Course]                      │  ← category badge
│                                     │
│  Butter Chicken                     │  ← name, 24px/700
│                                     │
│  PKR 250                            │  ← price, 20px/700, brandGreen
│                                     │
│  ● Available                        │  ← status dot + text
│                                     │
│  ─────────────────────────────────  │
│                                     │
│  DESCRIPTION                        │  ← section label
│  Rich creamy curry with tender      │
│  chicken pieces, simmered in a      │
│  blend of aromatic spices.          │
│                                     │
│  ─────────────────────────────────  │
│                                     │
│  🕐 ~15 min                         │  ← preparation time (if available)
│                                     │
│  ─────────────────────────────────  │
│                                     │
│  Dietary: Gluten-free               │  ← if available
│  Allergens: Dairy, Nuts             │  ← if available
│                                     │
├─────────────────────────────────────┤
│  ┌─────┐                            │
│  │  −  │   1   ┌──────────────────┐│
│  │     │       │  Add to cart ·   ││
│  │  +  │       │     PKR 250      ││
│  └─────┘       └──────────────────┘│
└─────────────────────────────────────┘
```

### 8.2 Element Specifications

| Element | Specification |
|---|---|
| Back button | Top-left, `< Arrow` icon (24px), 40×40 touch target |
| Image | Full width, `aspectRatio: 3/2`, `resizeMode: "cover"`, `borderRadius: 0` (edge-to-edge) |
| Image placeholder | Same dimensions, bgSecondary, centered category emoji (48px) |
| Category badge | `alignSelf: "flex-start"`, paddingHorizontal: 10, paddingVertical: 4, borderRadius: 6, bg: brandGreen+"15" (15% opacity), text: brandGreen, 12px/600 |
| Name | 24px, 700, letterSpacing: -0.3, textPrimary, `marginTop: 12` |
| Price | 20px, 700, brandGreen, `marginTop: 4` |
| Availability | 8×8 circle (green/red) + text (13px/600), `marginTop: 8` |
| Description label | "DESCRIPTION" — 12px, 600, uppercase, letterSpacing: 0.5, textMuted, `marginTop: 16` |
| Description text | 14px, 400, textSecondary, lineHeight: 20, `marginTop: 6` |
| Preparation time | 14px, 400, textMuted, `marginTop: 8` |
| Dietary/Allergens | 14px, 400, textSecondary, `marginTop: 8` |
| Bottom bar | `flexDirection: "row"`, `padding: 16`, `paddingBottom: 28` (safe area), borderTop: hairline, bg: bgPrimary |
| Quantity control | `flexDirection: "row"`, `borderRadius: 10`, `borderWidth: 1`, `borderColor: borderDefault`, `height: 48` |
| −/+ buttons | 48×48 touch target, textMuted text (when disabled: opacity 0.3) |
| Quantity value | 48px wide, centered, 16px/600 |
| Add to Cart button | `flex: 1`, `marginLeft: 12`, `height: 48`, `borderRadius: 10`, bg: brandGreen, white text (15px/600) |
| Button text | "Add to cart · PKR {price×qty}" — updates dynamically |
| Unavailable state | Bottom bar hidden. Show "Currently unavailable" banner instead. |

---

## 9. Cart Specification

### 9.1 Cart Bar (Floating — on Home/Menu screens)

```
┌─────────────────────────────────────┐
│  🛒  2 items              PKR 430 → │
└─────────────────────────────────────┘
```

| Property | Specification |
|---|---|
| Position | `position: "absolute"`, `bottom: 70` (above tab bar), `left: 16`, `right: 16` |
| Height | 52px |
| BorderRadius | 14 |
| Background | brandGreen |
| Shadow | `shadowColor: "#000"`, `shadowOffset: {0, 4}`, `shadowOpacity: 0.2`, `shadowRadius: 8`, `elevation: 8` |
| Cart icon | 🛒 or vector icon, 20px, white |
| Item count badge | bg: white, text: brandGreen (12px/700), `borderRadius: 10`, `paddingHorizontal: 6`, `paddingVertical: 2` |
| Count text | "{N} items" — 15px, 600, white |
| Total | "PKR {total}" — 16px, 700, white |
| Arrow | → 16px, white |

**Behavior:**
- Slides up from bottom when first item added (Animated.Translation)
- Slides down and hides when cart becomes empty
- Tap anywhere on bar → push Cart screen
- Haptic feedback on item add

### 9.2 Cart Screen

```
┌─────────────────────────────────────┐
│  ←  Cart                            │
├─────────────────────────────────────┤
│  Auto C1                            │  ← cafeteria name
│                                     │
│  ┌─────────────────────────────────┐│
│  │ 🖼️ Butter Chicken       − 2 +  ││
│  │    PKR 250 each         PKR 500 ││
│  │                        [Remove] ││
│  └─────────────────────────────────┘│
│  ┌─────────────────────────────────┐│
│  │ 🖼️ Chicken Biryani      − 1 +  ││
│  │    PKR 180 each         PKR 180 ││
│  │                        [Remove] ││
│  └─────────────────────────────────┘│
│                                     │
│  ┌─────────────────────────────────┐│
│  │  Subtotal            PKR 680   ││
│  │  ───────────────────────────── ││
│  │  Total               PKR 680   ││
│  └─────────────────────────────────┘│
│                                     │
│  ┌─────────────────────────────────┐│
│  │       Proceed to Checkout       ││
│  └─────────────────────────────────┘│
└─────────────────────────────────────┘
```

### 9.3 Cart Item Row

| Element | Specification |
|---|---|
| Container | `flexDirection: "row"`, `padding: 12`, `borderRadius: 12`, `bg: bgPrimary`, `marginBottom: 8` |
| Image thumbnail | 56×56, `borderRadius: 8`, `resizeMode: "cover"` |
| Image placeholder | 56×56, bgSecondary, centered category emoji (20px) |
| Content | `flex: 1`, `marginLeft: 12` |
| Name | 15px, 600, textPrimary, `numberOfLines: 1` |
| Unit price | 13px, 400, textMuted, "{price} each" |
| "Unavailable" label | 11px, 500, error color (shown when item no longer available) |
| Quantity control | `flexDirection: "row"`, `alignItems: "center"`, `gap: 0` |
| −/+ buttons | 32×32, borderRadius: 8, bg: bgSecondary, text: textPrimary (14px) |
| Quantity value | 32px wide, centered, 14px, 600 |
| Subtotal | 14px, 700, textPrimary, right-aligned |
| Remove button | "Remove" — 12px, 500, error color, below unit price (not a separate button, text tap) |

**Behavior:**
- Swipe left to reveal delete (future enhancement with react-native-gesture-handler)
- Quantity 1 → tapping "−" shows confirmation: "Remove item from cart?"
- Quantity max: 10 per item
- Unavailable items shown at reduced opacity (0.5) with warning

### 9.4 Cart Summary

| Element | Specification |
|---|---|
| Container | `padding: 16`, `borderRadius: 12`, `bg: bgPrimary`, `marginBottom: 12` |
| Subtotal row | "Subtotal" (14px, 400, textMuted) + "PKR {subtotal}" (14px, 500, textPrimary) |
| Divider | `StyleSheet.hairlineWidth`, borderDefault |
| Total row | "Total" (16px, 700, textPrimary) + "PKR {total}" (18px, 700, brandGreen) |

### 9.5 Checkout Button

| Element | Specification |
|---|---|
| Container | `padding: 16` |
| Button | Full width, height: 52, borderRadius: 12, bg: brandGreen |
| Text | "Proceed to Checkout" — 16px, 600, white |
| Disabled | When cart is empty or has unavailable items |

### 9.6 Empty Cart

```
┌─────────────────────────────────────┐
│  ←  Cart                            │
├─────────────────────────────────────┤
│                                     │
│              🛒                     │  ← 48px
│                                     │
│        Your cart is empty           │  ← 18px, 600
│                                     │
│   Add items from the menu to get    │  ← 14px, textMuted
│   started                           │
│                                     │
│      [ Browse Menu ]                │  ← primary button
│                                     │
└─────────────────────────────────────┘
```

---

## 10. Navigation Specification

### 10.1 Bottom Tab Bar

| Tab | Icon | Label | Active Color | Inactive Color |
|---|---|---|---|---|
| Home | Home (house) | Home | brandGreen | textMuted |
| My Orders | Clipboard/List | Orders | brandGreen | textMuted |
| Favorites | Heart (outline) | Favorites | brandGreen | textMuted |
| Profile | User | Profile | brandGreen | textMuted |

**Tab Bar Properties:**
| Property | Value |
|---|---|
| Height | 56px (+ safe area bottom) |
| Background | bgPrimary |
| Border top | `StyleSheet.hairlineWidth`, borderDefault |
| Active icon | 24px, brandGreen, filled variant |
| Active label | 10px, 600, brandGreen |
| Inactive icon | 24px, textMuted, outline variant |
| Inactive label | 10px, 400, textMuted |
| Badge on Orders | Red dot (8×8) when there are active/pending orders |

**Icon Library:** Use `@expo/vector-icons` (Ionicons) — already available in Expo SDK 51. No new dependency needed.

| Tab | Active Icon | Inactive Icon |
|---|---|---|
| Home | `home` | `home-outline` |
| Orders | `receipt` | `receipt-outline` |
| Favorites | `heart` | `heart-outline` |
| Profile | `person` | `person-outline` |

### 10.2 Header Pattern (Pushed Screens)

| Screen | Header Style |
|---|---|
| Home | No header — content starts at top (status bar padding) |
| Item Detail | Transparent header with back arrow |
| Cart | Back arrow + "Cart" title |
| Orders | No header — content starts at top |
| Profile | No header — content starts at top |

### 10.3 Screen Transitions

| Transition | Animation |
|---|---|
| Tab switch | Cross-fade (default expo-router) |
| Push (Home → Item Detail) | Slide from right (default iOS) |
| Push (Cart Bar → Cart) | Slide from bottom (modal feel) |
| Modal (future) | Slide up from bottom, dimmed backdrop |

---

## 11. Color System

### 11.1 Redesigned Palette

The current palette is functional but the brand green is overused. The redesign distributes visual weight more carefully.

#### Primary Brand Colors

| Token | Hex | Role | Usage |
|---|---|---|---|
| `brandGreen` | `#005400` | Primary CTA, active tab, price emphasis | ~10% of screen |
| `brandGreenLight` | `#0d7a2e` | Hover states, secondary green | Rarely |
| `brandGold` | `#ffc000` | Special badges, featured items, premium | ~3% of screen |

#### Neutral System

| Token | Light Mode | Dark Mode | Role |
|---|---|---|---|
| `bgPrimary` | `#ffffff` | `#0f1218` | Screen background |
| `bgSecondary` | `#f5f5f7` | `#1a1f2e` | Cards, search bar, chip bg |
| `bgTertiary` | `#ebedf0` | `#252b3b` | Subtle backgrounds |
| `textPrimary` | `#1a1c20` | `#f0f1f4` | Headings, names, prices |
| `textSecondary` | `#4a4e57` | `#b0b5be` | Body text, descriptions |
| `textMuted` | `#8a8f98` | `#6b7280` | Captions, placeholders |
| `borderDefault` | `#e2e4e8` | `#2a3042` | Card borders, dividers |
| `borderSubtle` | `#f0f1f3` | `#1e2433` | Hairline dividers |

#### Functional Colors

| Token | Hex | Role |
|---|---|---|
| `success` | `#16a34a` | Available, open, confirmed |
| `warning` | `#f59e0b` | Closing soon, pending |
| `error` | `#dc2626` | Unavailable, closed, out of stock |
| `info` | `#2563eb` | Informational |
| `surface` | `#f5f5f7` | Light surface |

### 11.2 Color Usage Rules

1. **BrandGreen** appears in: primary CTA button, active tab icon, price text, "Add to cart" button background
2. **BrandGold** appears in: "Today's Special" badge, featured item highlight, premium indicator
3. **Backgrounds** should be predominantly neutral (white/light gray). Food photos provide color.
4. **Never use brandGreen as a background color** for large areas (creates a "green wall" effect)
5. **Error/warning colors** should be theme-aware (current hardcoded values break dark mode)

### 11.3 What Changes from Current

| Current | Redesigned | Reason |
|---|---|---|
| Cart bar bg: brandGreen | Same | Cart CTA = brand identity |
| Price text: brandGreen | Same | Consistent price emphasis |
| Avatar bg: brandGreen | `bgSecondary` with brandGreen initials | Less green mass |
| Role badge: brandGreen bg | `bgSecondary` bg, brandGreen text | Less green mass |
| Category chip active: brandGreen bg | Same | Clear active indicator |
| Tab active: brandGreen | Same | Standard navigation |
| Notification bell: bgTertiary circle | bgSecondary circle | Softer |
| Error banner: hardcoded `#fef2f2` | Theme-aware error surface | Dark mode support |

---

## 12. Typography

### 12.1 Type Scale

| Role | Size | Weight | Line Height | Letter Spacing | Usage |
|---|---|---|---|---|---|
| `display` | 28 | 700 | 34 | -0.5 | Greeting ("Good morning, Test") |
| `title` | 22 | 700 | 28 | -0.3 | Screen titles |
| `heading` | 18 | 700 | 24 | -0.2 | Section headings |
| `subheading` | 16 | 600 | 22 | 0 | Item names, card titles |
| `body` | 15 | 400 | 20 | 0 | Descriptions, body text |
| `bodySmall` | 13 | 400 | 18 | 0 | Secondary descriptions, metadata |
| `caption` | 12 | 400 | 16 | 0 | Timestamps, status labels |
| `price` | 16 | 700 | 20 | 0 | Price display |
| `priceLarge` | 20 | 700 | 24 | 0 | Item detail price |
| `label` | 13 | 600 | 16 | 0 | Category labels, chip text |
| `badge` | 11 | 700 | 14 | 0.5 | Uppercase badges (SPECIAL, NEW) |
| `button` | 15 | 600 | 20 | 0 | Button text |
| `buttonSmall` | 13 | 600 | 18 | 0 | Small button text |
| `tabLabel` | 10 | 500 | 14 | 0 | Bottom tab labels |

### 12.2 Font Family

- **Primary:** System font (San Francisco on iOS, Roboto on Android)
- **Rationale:** No custom font needed. System fonts are fast, familiar, and automatically adapt to the platform. The current Inter font in the web app is fine for web, but React Native apps benefit from system fonts for performance and native feel.
- **Alternative:** If brand consistency with the web app is required, `@expo-google-fonts/inter` can be loaded (adds ~200KB to bundle).

### 12.3 Typography Rules

1. **Prices always use the `price` style** — consistent size, weight, and brandGreen color
2. **Item names truncate at 1 line** in cards, 2 lines max in detail
3. **Descriptions truncate at 1 line** in cards, unlimited in detail
4. **Section labels are always uppercase** with letter spacing
5. **Never use font weight below 400** for body text (readability)
6. **Minimum font size: 11px** (below this is unreadable on mobile)

---

## 13. Motion Principles

### 13.1 Animation Rules

1. **Functional, not decorative** — every animation communicates state change
2. **Fast** — 150-300ms for most transitions
3. **Eased** — use `Easing.bezier(0.4, 0, 0.2, 1)` (material standard)
4. **Subtle** — never distract from content

### 13.2 Defined Micro-Interactions

| Interaction | Animation | Duration | Library |
|---|---|---|---|
| **Add to cart** | Button scale-down (0.95→1) + toast slide-in from top | 200ms + 300ms | `Animated` + `LayoutAnimation` |
| **Cart bar appears** | Slide up from bottom | 250ms | `Animated.Translation` |
| **Cart bar updates** | Count number bounce (scale 1→1.2→1) | 200ms | `Animated.spring` |
| **Category chip select** | Background fill transition | 150ms | `Animated.timing` |
| **Quantity change** | Number crossfade | 100ms | `LayoutAnimation` |
| **Card press** | Scale to 0.98 | 100ms | `activeOpacity={0.98}` |
| **Pull to refresh** | Custom branded spinner | — | `RefreshControl` |
| **Screen transition** | Slide from right (push), slide from bottom (cart) | 300ms | expo-router default |
| **Skeleton shimmer** | Horizontal gradient sweep | 1200ms loop | `Animated` with linear gradient |
| **Toast dismiss** | Slide up + fade out | 200ms | `Animated` |

### 13.3 What We Do NOT Animate

- Loading spinners (just show/hide)
- Tab bar appearance (always visible)
- Text content changes (instant)
- Screen content on first load (no entrance animations for lists)

---

## 14. Empty / Error / Loading States

### 14.1 Empty States

#### Empty Cart

```
         🛒
   Your cart is empty
  Add items from the menu
     to get started

     [ Browse Menu ]
```

| Element | Specification |
|---|---|
| Icon | Cart vector icon (48px, textMuted) |
| Title | "Your cart is empty" — 18px, 600, textPrimary |
| Description | "Add items from the menu to get started" — 14px, 400, textMuted |
| CTA | "Browse Menu" — primary button, navigates to Home tab |

#### No Menu Published

```
         📋
     Menu not available
  Today's menu hasn't been
  published yet. Check back
      later!
```

| Element | Specification |
|---|---|
| Icon | Clipboard vector icon (48px, textMuted) |
| Title | "Menu not available" — 18px, 600, textPrimary |
| Description | "Today's menu hasn't been published yet. Check back later!" — 14px, 400, textMuted |
| No CTA | (nothing to browse) |

#### Cafeteria Closed

```
         🔒
     We're closed
  This cafeteria is currently
  closed. Check operating hours
  for next opening time.
```

| Element | Specification |
|---|---|
| Icon | Lock vector icon (48px, textMuted) |
| Title | "We're closed" — 18px, 600, textPrimary |
| Description | "This cafeteria is currently closed. Check operating hours for next opening time." — 14px, 400, textMuted |
| No CTA | (cannot order when closed) |

#### No Search Results

```
         🔍
     No items found
  No items match "{query}"
```

| Element | Specification |
|---|---|
| Icon | Search vector icon (48px, textMuted) |
| Title | "No items found" — 18px, 600, textPrimary |
| Description | `No items match "{query}"` — 14px, 400, textMuted |
| CTA | "Clear search" — secondary button |

#### Empty Orders

```
         📋
     No orders yet
  Your order history will
  appear here after your
  first order.
```

| Element | Specification |
|---|---|
| Icon | Clipboard vector icon (48px, textMuted) |
| Title | "No orders yet" — 18px, 600, textPrimary |
| Description | "Your order history will appear here after your first order." — 14px, 400, textMuted |
| No CTA | |

#### Empty Favorites

```
         ❤️
     No favorites yet
  Save your favorite items
  for quick reordering.
```

| Element | Specification |
|---|---|
| Icon | Heart outline vector icon (48px, textMuted) |
| Title | "No favorites yet" — 18px, 600, textPrimary |
| Description | "Save your favorite items for quick reordering." — 14px, 400, textMuted |
| No CTA | |

#### No Items in Category

```
         🍽️
     Nothing here yet
  No items available in this
  category today.
```

| Element | Specification |
|---|---|
| Icon | Utensils vector icon (48px, textMuted) |
| Title | "Nothing here yet" — 18px, 600, textPrimary |
| Description | "No items available in this category today." — 14px, 400, textMuted |
| No CTA | |

### 14.2 Error States

#### API Failure / Network Error

```
         ⚠️
     Something went wrong
  We couldn't load the menu.
  Please check your connection
  and try again.

      [ Try Again ]
```

| Element | Specification |
|---|---|
| Icon | Warning vector icon (48px, error color) |
| Title | "Something went wrong" — 18px, 600, textPrimary |
| Description | "We couldn't load the menu. Please check your connection and try again." — 14px, 400, textMuted |
| CTA | "Try Again" — primary button (retries the failed request) |

#### Item Load Error

```
         😵
     Item not found
  This item may have been
  removed from the menu.

     [ Go Back ]
```

| Element | Specification |
|---|---|
| Icon | "—" (no emoji, just a simple circle icon, 48px, textMuted) |
| Title | "Item not found" — 18px, 600, textPrimary |
| Description | "This item may have been removed from the menu." — 14px, 400, textMuted |
| CTA | "Go Back" — secondary button |

#### Item Unavailable (on detail screen)

```
┌─────────────────────────────────────┐
│  ⚠️ Currently unavailable           │
│  This item is not available today.  │
└─────────────────────────────────────┘
```

| Element | Specification |
|---|---|
| Container | Full width, padding: 14, borderRadius: 10, bg: warning surface, marginBottom: 12 |
| Text | "Currently unavailable" — 14px, 500, warning text color |
| Subtext | "This item is not available today." — 13px, 400, textMuted |
| Add to Cart button | Hidden (replaced by this banner) |

### 14.3 Loading States

#### Skeleton Loading (Menu Grid)

```
┌─────────────────┐  ┌─────────────────┐
│  ┌────────────┐ │  │  ┌────────────┐ │
│  │ ░░░░░░░░░░ │ │  │  │ ░░░░░░░░░░ │ │
│  │ ░░░░░░░░░░ │ │  │  │ ░░░░░░░░░░ │ │
│  └────────────┘ │  │  └────────────┘ │
│  ░░░░░░░░░░░░░  │  │  ░░░░░░░░░░░░░  │
│  ░░░░░░░░░░     │  │  ░░░░░░░░░░     │
│  ░░░░░░  ░░░░░  │  │  ░░░░░░  ░░░░░  │
└─────────────────┘  └─────────────────┘
```

| Property | Specification |
|---|---|
| Image placeholder | Square (aspectRatio 1), bg: bgTertiary, borderRadius: 12 |
| Text lines | 2-3 bars, bg: bgTertiary, borderRadius: 4, height: 12-14px |
| Shimmer animation | Horizontal gradient sweep, 1200ms loop |
| Pattern | 4 skeleton cards in 2-column grid |

#### Full-screen Loading (Initial)

| Property | Specification |
|---|---|
| Indicator | ActivityIndicator, brandGreen, large |
| Label | "Loading..." — 14px, textMuted |
| Background | bgPrimary (no overlay) |

---

## 15. Dark Mode

### 15.1 Design Principles

1. **Not an inversion** — dark mode uses a carefully designed palette, not just swapped colors
2. **True dark, not gray** — backgrounds use near-black with slight blue tint (`#0f1218`)
3. **Reduced contrast** — text uses slightly softer white (`#f0f1f4` instead of pure white)
4. **Preserved brand** — brandGreen and brandGold remain identical
5. **Food images unchanged** — food photography works on both light and dark backgrounds
6. **Surface elevation** — higher surfaces are lighter (reverse of light mode)

### 15.2 Dark Mode Palette

| Token | Light Mode | Dark Mode |
|---|---|---|
| `bgPrimary` | `#ffffff` | `#0f1218` |
| `bgSecondary` | `#f5f5f7` | `#1a1f2e` |
| `bgTertiary` | `#ebedf0` | `#252b3b` |
| `textPrimary` | `#1a1c20` | `#f0f1f4` |
| `textSecondary` | `#4a4e57` | `#b0b5be` |
| `textMuted` | `#8a8f98` | `#6b7280` |
| `borderDefault` | `#e2e4e8` | `#2a3042` |
| `borderSubtle` | `#f0f1f3` | `#1e2433` |
| `brandGreen` | `#005400` | `#22c55e` (brighter for contrast) |
| `brandGold` | `#ffc000` | `#ffc000` (unchanged) |
| `error` | `#dc2626` | `#f87171` (lighter for contrast) |
| `warning` | `#f59e0b` | `#fbbf24` |
| `success` | `#16a34a` | `#4ade80` |
| `cartBarBg` | `#005400` | `#16a34a` (brighter green for dark bg) |

### 15.3 Dark Mode Specifics

| Element | Light Mode | Dark Mode |
|---|---|---|
| Screen bg | White | Near-black |
| Card bg | White with border | Slightly lighter than bg, no border (subtle elevation) |
| Tab bar bg | White | bgPrimary with subtle top border |
| Search bar | bgSecondary | bgTertiary |
| Skeleton shimmer | bgTertiary → bgSecondary | bgTertiary → bgSecondary |
| Error banner | Light red bg | Semi-transparent red bg |
| Status bar | Dark icons | Light images |

### 15.4 Dark Mode Toggle

The toggle should be accessible from the Profile screen:
- "Appearance" row in the settings section
- Options: "System" (default), "Light", "Dark"
- Persisted to SecureStorage
- Applies immediately (no app restart)

---

## 16. Mobile Usability Principles

### 16.1 One-Handed Use

| Principle | Implementation |
|---|---|
| **Primary actions in bottom 60%** | Cart bar, tab bar, Add to Cart button all in bottom zone |
| **Navigation at bottom** | Bottom tab bar (not top tabs) |
| **Search accessible** | Below header, not hidden behind hamburger menu |
| **Back gesture** | Swipe from left edge (iOS standard) |

### 16.2 Touch Targets

| Element | Minimum Size | Recommended Size |
|---|---|---|
| Tab bar icons | 24×24 | 44×44 touch area |
| Cart bar | Full width | 52px height |
| Add to cart (+) | 28×28 | 44×44 touch area |
| Category chips | Auto width | 44px height |
| Quantity −/+ | 32×32 | 44×44 touch area |
| Back button | 24×24 | 44×44 touch area |
| Search bar | Full width | 44px height |
| Remove item | 24×24 text | 44×44 touch area |

### 16.3 Scrolling

| Pattern | Implementation |
|---|---|
| **Menu grid** | Vertical scroll, `FlatList` for performance |
| **Categories** | Horizontal scroll with snap points |
| **Pull-to-refresh** | On Home screen and Orders screen |
| **Scroll to top** | Tap active tab to scroll Home to top |
| **Infinite scroll** | Not needed (daily menu is finite) |

### 16.4 Keyboard / Search

| Behavior | Implementation |
|---|---|
| **Search auto-focus** | Tap search bar → keyboard opens, content scrolls up |
| **Keyboard dismiss** | Tap outside search or clear button |
| **Results update** | As user types (debounced 300ms) |
| **No submit button** | Search is instant, no keyboard return action needed |
| **Category visible** | Categories scroll out of view when keyboard is open (acceptable) |

### 16.5 Accessibility

| Principle | Implementation |
|---|---|
| **Minimum contrast** | 4.5:1 for body text, 3:1 for large text |
| **Touch labels** | Every interactive element has an `accessibilityLabel` |
| **Role hints** | `accessibilityRole` set for buttons, links, headers |
| **Dynamic type** | Support system font scaling (within reason — cap at 1.5×) |
| **Color independence** | Never use color alone to convey status (always pair with text/icon) |

---

## 17. Implementation Slices

### Slice 1: Foundation & Navigation (Current — Completed)

**Status:** ✅ Implemented and verified  
**Scope:** Login, Home (basic), Orders (basic), Profile, Cart (basic), Item Detail (basic)  
**Focus:** Auth flow, API integration, navigation skeleton

### Slice 2: Visual Redesign

**Status:** 🔲 Not started  
**Scope:**
- Replace emoji icons with `@expo/vector-icons` (Ionicons)
- Implement 2-column food grid on Home
- Redesign food cards with image placeholder
- Redesign header (greeting + cafeteria context)
- Redesign search bar
- Redesign category chips
- Update color system (theme-aware)
- Update typography system
- Fix Card component for dark mode
- Add "Browse Menu" CTA to empty cart

**Files to modify:**
- `app/(tabs)/index.tsx` (Home — major rewrite)
- `app/(tabs)/_layout.tsx` (Tab bar — new icons, 4 tabs)
- `app/item/[id].tsx` (Item detail — new layout)
- `app/cart.tsx` (Cart — new layout)
- `src/components/ui/Card.tsx` (theme-aware)
- `src/components/ui/EmptyState.tsx` (new design)
- `src/theme/colors.ts` (updated palette)
- `src/theme/typography.ts` (updated scale)
- New: `src/components/FoodCard.tsx`
- New: `src/components/SearchBar.tsx`
- New: `src/components/CategoryChips.tsx`
- New: `src/components/CafeteriaBadge.tsx`
- New: `src/components/CartBar.tsx`
- New: `app/(tabs)/favorites.tsx` (empty state placeholder)

### Slice 3: Food Imagery

**Status:** 🔲 Not started  
**Scope:**
- Implement `FoodImage` component with placeholder + real image support
- Backend: Add image upload endpoint (or S3/Cloudinary integration)
- Seed data: Add sample food images for testing
- Item detail: Full-width food photo
- Cart: Food thumbnails in cart rows

**Dependencies:** Backend image storage decision (see §7.3 of Food Imagery below)

### Slice 4: Cart & Checkout

**Status:** 🔲 Not started  
**Scope:**
- Swipe-to-delete in cart
- Checkout flow (payment method selection)
- Order confirmation screen
- Order tracking/progress UI

### Slice 5: Orders & Reorder

**Status:** 🔲 Not started  
**Scope:**
- Enhanced order list with item previews
- Order detail screen
- "Order Again" quick reorder
- Order status tracking with progress indicators
- Push notification integration

### Slice 6: Favorites & Polish

**Status:** 🔲 Not started  
**Scope:**
- Favorites functionality (save/unsave items)
- Favorites screen with grid
- Skeleton loading everywhere
- Micro-interactions (add-to-cart toast, quantity bounce)
- Performance optimization
- Accessibility audit

---

## 18. Non-Goals

The following are explicitly **NOT** part of this redesign or the mobile app scope:

| Non-Goal | Rationale |
|---|---|
| **Payment processing** | Not implemented in this project |
| **Delivery tracking** | Campus pickup model, no delivery |
| **Ratings/reviews** | Reviews are internal admin data, not public |
| **Item customization** | No modifiers/variants in the data model |
| **Multi-restaurant delivery** | Single cafeteria context per order |
| **Push notifications** | Future slice, not part of visual redesign |
| **Meal plan integration** | No meal plan data model exists |
| **Social features** | No friend ordering, sharing, or social feed |
| **Admin dashboard** | Separate web application |
| **Table reservation** | Not a cafeteria feature |
| **Loyalty/rewards** | Future consideration, not current scope |
| **Voice ordering** | Out of scope |
| **AR food preview** | Out of scope |
| **White-label theming** | Single brand (LGU) |
| **Offline mode** | Requires network for menu, cart, orders |
| **iPad/tablet layout** | Phone-first, tablet is future consideration |

---

## Appendix A: Food Imagery Strategy

### Current State

| Question | Answer |
|---|---|
| Does MenuItem have `image_url`? | ✅ Yes — `String(512)`, nullable, in model, schemas, service, shared types, and migration |
| Does DailyMenuItem have image fields? | ❌ No — junction table only |
| Image upload/storage endpoints? | ❌ None — `image_url` is just a URL string in JSON |
| Seed data with image URLs? | ❌ None — all test fixtures create items without images |
| S3/Cloudinary/file storage? | ❌ No references anywhere in the backend |

### Recommendation

**Phase 1 (Slice 2): Placeholder System**
- Use category-based colored backgrounds with food emoji as placeholder
- Design the `FoodImage` component to accept `image_url` and gracefully fall back to placeholder
- This makes the app visually functional immediately

**Phase 2 (Slice 3): Image Integration**
- Option A (Recommended): **Unsplash API** — free tier, high-quality food photos, no storage needed
  - Use `source.unsplash.com/300x300/?biryani` style URLs
  - Cache locally with `expo-image` for performance
  - No backend changes needed — set `image_url` to Unsplash URLs via admin
- Option B: **Cloudinary** — free tier, more control, requires backend integration
- Option C: **Local assets** — bundle food photos in the app (not scalable)
- Option D: **Admin upload** — build an upload endpoint (most work, most flexible)

**For Slice 2, no image changes are needed.** The placeholder system (colored bg + category icon) is visually acceptable and allows the redesign to proceed without backend changes.

---

## Appendix B: Component Inventory (New & Modified)

### New Components

| Component | File | Purpose |
|---|---|---|
| `FoodCard` | `src/components/FoodCard.tsx` | 2-column grid food card with image, name, price, add-to-cart |
| `FoodCardList` | `src/components/FoodCardList.tsx` | Single-column list card for search results |
| `FoodImage` | `src/components/FoodImage.tsx` | Image with placeholder fallback |
| `SearchBar` | `src/components/SearchBar.tsx` | Search input with icon and clear |
| `CategoryChips` | `src/components/CategoryChips.tsx` | Horizontal scrolling category filter |
| `CafeteriaBadge` | `src/components/CafeteriaBadge.tsx` | Cafeteria name + location + status |
| `CartBar` | `src/components/CartBar.tsx` | Floating cart summary bar |
| `CartItemRow` | `src/components/CartItemRow.tsx` | Cart item with image, quantity, subtotal |
| `EmptyState` | `src/components/ui/EmptyState.tsx` | Redesigned empty state (updated) |
| `SkeletonCard` | `src/components/SkeletonCard.tsx` | Skeleton loading placeholder |
| `Toast` | `src/components/Toast.tsx` | "Added to cart" notification |

### Modified Components

| Component | Changes |
|---|---|
| `Button` | Add `fullWidth` prop, update border radius to 10/12 |
| `Card` | Make theme-aware (currently hardcoded white) |
| `Spinner` | Rename to `LoadingSpinner`, add skeleton variant |
| `StatusChip` | Theme-aware colors |

---

## Appendix C: Icon System

### Current State
- 0 vector icons — all 24+ icon usages are emoji
- No icon library installed

### Recommended: `@expo/vector-icons` (Ionicons)

Already available in Expo SDK 51. No new dependency. Provides 1,200+ icons.

| Context | Current Emoji | Replacement Icon |
|---|---|---|
| Home tab (active) | 🏠 | `home` |
| Home tab (inactive) | — | `home-outline` |
| Orders tab (active) | 📋 | `receipt` |
| Orders tab (inactive) | — | `receipt-outline` |
| Favorites tab (active) | ❤️ | `heart` |
| Favorites tab (inactive) | — | `heart-outline` |
| Profile tab (active) | 👤 | `person` |
| Profile tab (inactive) | — | `person-outline` |
| Notification bell | 🔔 | `notifications-outline` |
| Search | 🔍 | `search` |
| Search clear | ✕ | `close-circle` |
| Back arrow | ← | `arrow-back` |
| Cart bar arrow | → | `arrow-forward` |
| Cart | 🛒 | `cart` |
| Empty cart | 🛒 | `cart-outline` |
| Empty orders | 📋 | `document-text-outline` |
| Empty favorites | ❤️ | `heart-outline` |
| Empty search | 🔍 | `search-outline` |
| Error | ⚠️ | `alert-circle` |
| Cafeteria | 🍽️ | `restaurant-outline` |
| Add (+) | + | `add` |
| Remove (−) | − | `remove` |
| Close | — | `close` |
| Check/Verified | ✓ | `checkmark-circle` |
| Lock (closed) | — | `lock-closed` |
| Clock (time) | 🕐 | `time-outline` |
| Chevron right | → | `chevron-forward` |

**Food category icons** — keep emoji for categories. They are distinctive, colorful, and universally understood for food types. Vector icons cannot match the expressiveness of 🍛 🍳 🥗 🍰 ☕ 🍿 🥬 🍜 for food categorization.

---

*End of specification.*
