# Quathera Form Manager - Electron Desktop App

A comprehensive form management desktop application built with Electron.

## 🚀 Quick Start

### Prerequisites
- Node.js 18+ installed
- npm or yarn

### Installation

```bash
# Navigate to the project directory
cd electron-form-app

# Install dependencies
npm install

# Run the application
npm start

# Run with DevTools open
npm start -- --dev
```

## 📦 Building for Distribution

### Build for Current Platform
```bash
npm run build
```

### Build for Specific Platforms
```bash
# Windows
npm run build:win

# macOS
npm run build:mac

# Linux
npm run build:linux
```

Built packages will be in the `dist/` folder.

## 🎯 Features

### Form Management
- ✅ Create new forms with comprehensive fields
- ✅ View saved forms in a table layout
- ✅ Edit existing forms
- ✅ Delete forms with confirmation

### Form Fields Include
- **Basic Info**: Name, Email, Phone, Date of Birth
- **File Uploads**: Profile Image, PDF Documents
- **Conditional Fields**: Enterprise-specific fields (Company Name, Tax ID, Manager info)
- **Dynamic Lists**: Findings & Engagements (Add/Edit/Delete)
- **Calculations**: Income Bruto/Neto with tax percentage
- **Special Inputs**: Star rating (Shadow DOM), Range slider, Multi-select

### Advanced Features
- 📁 **Nested iframes** - 2 levels deep for address/contact forms
- 🌟 **Shadow DOM** - Encapsulated rating widget
- 💼 **Job Description Modal** - Pop-up form entry
- 📊 **Enterprise Mode** - Special greeting and additional fields
- 💾 **Data Persistence** - localStorage with Export/Import support

### Desktop Features
- 📤 **Export Data** - Save forms to JSON file (Ctrl+E)
- 📥 **Import Data** - Load forms from JSON file (Ctrl+I)
- 🔄 **Merge or Replace** - Choose how to import data
- ⌨️ **Keyboard Shortcuts** - Ctrl+N (New), Ctrl+L (List), F12 (DevTools)

## 🗂️ Project Structure

```
electron-form-app/
├── main.js              # Electron main process
├── preload.js           # Preload script (context bridge)
├── package.json         # Dependencies & build config
├── index.html           # Main page (Form Manager)
├── test-form.html       # Form creation/editing
├── view-form.html       # Form viewing
├── address-form.html    # Address iframe
├── contact-form.html    # Emergency contact iframe
├── terms-handler.js     # External JS for terms checkbox
└── assets/
    └── icon.svg         # App icon
```

## ⌨️ Keyboard Shortcuts

| Shortcut | Action |
|----------|--------|
| Ctrl+N | New Form |
| Ctrl+L | View All Forms |
| Ctrl+E | Export Data |
| Ctrl+I | Import Data |
| F12 | Toggle DevTools |
| Ctrl+R | Reload |
| Ctrl+Q | Quit (Cmd+Q on macOS) |

## 🔧 Menu Options

### File Menu
- New Form
- View All Forms
- Export Data
- Import Data
- Exit

### Edit Menu
- Undo, Redo, Cut, Copy, Paste, Select All

### View Menu
- Reload, Zoom controls, Fullscreen, DevTools

### Help Menu
- About

## 📝 Data Storage

Forms are stored in localStorage within the Electron app. You can:
- **Export** to a JSON file for backup
- **Import** from a JSON file (replace all or merge)

## 🧪 Testing Form Discoverer

This app is perfect for testing Quathera's Form Discoverer because it includes:

1. **Multiple input types**: text, email, tel, date, file, select, textarea, checkbox, radio, range, multi-select
2. **Nested structures**: iframes 2 levels deep
3. **Shadow DOM**: Encapsulated components
4. **Dynamic content**: JavaScript-generated fields
5. **Modals**: Pop-up dialogs
6. **Hover menus**: Hidden form fields
7. **Conditional logic**: Fields that appear based on selection
8. **Calculated fields**: Auto-computed values
9. **External JavaScript**: Separate JS file handling

## 🐛 Troubleshooting

### App won't start
```bash
# Clear node_modules and reinstall
rm -rf node_modules
npm install
```

### Blank screen
Check the DevTools console (F12) for errors.

### Build fails
Make sure you have the required build tools:
- Windows: `npm install --global windows-build-tools`
- macOS: Xcode Command Line Tools
- Linux: `build-essential` package

## 📄 License

MIT License - Quathera © 2024
