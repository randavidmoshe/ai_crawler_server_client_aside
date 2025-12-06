const { app, BrowserWindow, Menu, ipcMain, dialog } = require('electron');
const path = require('path');
const fs = require('fs');

// Keep a global reference of the window object
let mainWindow;

// Data storage path
const userDataPath = app.getPath('userData');
const dataFilePath = path.join(userDataPath, 'savedForms.json');

function createWindow() {
    // Create the browser window
    mainWindow = new BrowserWindow({
        width: 1400,
        height: 900,
        minWidth: 800,
        minHeight: 600,
        icon: path.join(__dirname, 'assets', 'icon.png'),
        webPreferences: {
            nodeIntegration: false,
            contextIsolation: true,
            preload: path.join(__dirname, 'preload.js')
        },
        titleBarStyle: 'default',
        show: false // Don't show until ready
    });

    // Load the index.html
    mainWindow.loadFile('index.html');

    // Show window when ready to prevent visual flash
    mainWindow.once('ready-to-show', () => {
        mainWindow.show();
    });

    // Open DevTools in development
    if (process.argv.includes('--dev')) {
        mainWindow.webContents.openDevTools();
    }

    // Handle window close
    mainWindow.on('closed', () => {
        mainWindow = null;
    });

    // Create application menu
    createMenu();
}

function createMenu() {
    const template = [
        {
            label: 'File',
            submenu: [
                {
                    label: 'New Form',
                    accelerator: 'CmdOrCtrl+N',
                    click: () => {
                        mainWindow.loadFile('test-form.html');
                    }
                },
                {
                    label: 'View All Forms',
                    accelerator: 'CmdOrCtrl+L',
                    click: () => {
                        mainWindow.loadFile('index.html');
                    }
                },
                { type: 'separator' },
                {
                    label: 'Export Data',
                    accelerator: 'CmdOrCtrl+E',
                    click: async () => {
                        await exportData();
                    }
                },
                {
                    label: 'Import Data',
                    accelerator: 'CmdOrCtrl+I',
                    click: async () => {
                        await importData();
                    }
                },
                { type: 'separator' },
                {
                    label: 'Exit',
                    accelerator: process.platform === 'darwin' ? 'Cmd+Q' : 'Alt+F4',
                    click: () => {
                        app.quit();
                    }
                }
            ]
        },
        {
            label: 'Edit',
            submenu: [
                { role: 'undo' },
                { role: 'redo' },
                { type: 'separator' },
                { role: 'cut' },
                { role: 'copy' },
                { role: 'paste' },
                { role: 'selectall' }
            ]
        },
        {
            label: 'View',
            submenu: [
                { role: 'reload' },
                { role: 'forceReload' },
                { type: 'separator' },
                { role: 'resetZoom' },
                { role: 'zoomIn' },
                { role: 'zoomOut' },
                { type: 'separator' },
                { role: 'togglefullscreen' },
                { type: 'separator' },
                {
                    label: 'Toggle Developer Tools',
                    accelerator: 'F12',
                    click: () => {
                        mainWindow.webContents.toggleDevTools();
                    }
                }
            ]
        },
        {
            label: 'Help',
            submenu: [
                {
                    label: 'About Quathera Form Manager',
                    click: () => {
                        dialog.showMessageBox(mainWindow, {
                            type: 'info',
                            title: 'About',
                            message: 'Quathera Form Manager',
                            detail: 'Version 1.0.0\n\nA comprehensive form management system for testing and data collection.\n\n© 2024 Quathera'
                        });
                    }
                }
            ]
        }
    ];

    // macOS specific menu adjustments
    if (process.platform === 'darwin') {
        template.unshift({
            label: app.getName(),
            submenu: [
                { role: 'about' },
                { type: 'separator' },
                { role: 'services' },
                { type: 'separator' },
                { role: 'hide' },
                { role: 'hideOthers' },
                { role: 'unhide' },
                { type: 'separator' },
                { role: 'quit' }
            ]
        });
    }

    const menu = Menu.buildFromTemplate(template);
    Menu.setApplicationMenu(menu);
}

async function exportData() {
    try {
        const result = await dialog.showSaveDialog(mainWindow, {
            title: 'Export Forms Data',
            defaultPath: `forms-export-${new Date().toISOString().split('T')[0]}.json`,
            filters: [
                { name: 'JSON Files', extensions: ['json'] },
                { name: 'All Files', extensions: ['*'] }
            ]
        });

        if (!result.canceled && result.filePath) {
            // Get data from renderer process
            mainWindow.webContents.executeJavaScript('localStorage.getItem("savedForms") || "[]"')
                .then(data => {
                    fs.writeFileSync(result.filePath, data, 'utf-8');
                    dialog.showMessageBox(mainWindow, {
                        type: 'info',
                        title: 'Export Successful',
                        message: `Data exported successfully to:\n${result.filePath}`
                    });
                });
        }
    } catch (error) {
        dialog.showErrorBox('Export Error', error.message);
    }
}

async function importData() {
    try {
        const result = await dialog.showOpenDialog(mainWindow, {
            title: 'Import Forms Data',
            filters: [
                { name: 'JSON Files', extensions: ['json'] },
                { name: 'All Files', extensions: ['*'] }
            ],
            properties: ['openFile']
        });

        if (!result.canceled && result.filePaths.length > 0) {
            const data = fs.readFileSync(result.filePaths[0], 'utf-8');
            
            // Validate JSON
            JSON.parse(data);
            
            // Confirm import
            const confirm = await dialog.showMessageBox(mainWindow, {
                type: 'question',
                buttons: ['Replace All', 'Merge', 'Cancel'],
                defaultId: 2,
                title: 'Import Data',
                message: 'How would you like to import the data?',
                detail: 'Replace All: Delete existing data and import new data\nMerge: Add imported data to existing data'
            });

            if (confirm.response === 0) {
                // Replace all
                await mainWindow.webContents.executeJavaScript(`localStorage.setItem("savedForms", '${data.replace(/'/g, "\\'")}'); location.reload();`);
            } else if (confirm.response === 1) {
                // Merge
                await mainWindow.webContents.executeJavaScript(`
                    const existing = JSON.parse(localStorage.getItem("savedForms") || "[]");
                    const imported = JSON.parse('${data.replace(/'/g, "\\'")}');
                    const merged = [...existing, ...imported];
                    localStorage.setItem("savedForms", JSON.stringify(merged));
                    location.reload();
                `);
            }
        }
    } catch (error) {
        dialog.showErrorBox('Import Error', `Failed to import data: ${error.message}`);
    }
}

// App lifecycle events
app.whenReady().then(createWindow);

app.on('window-all-closed', () => {
    if (process.platform !== 'darwin') {
        app.quit();
    }
});

app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) {
        createWindow();
    }
});

// Handle any uncaught exceptions
process.on('uncaughtException', (error) => {
    console.error('Uncaught Exception:', error);
    dialog.showErrorBox('Error', error.message);
});
