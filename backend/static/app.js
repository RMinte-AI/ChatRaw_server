// JustChat - Minimalist AI Chat Application

// Lazy load highlight.js for better performance
let hljsLoaded = false;
let hljsLoading = false;

async function loadHighlightJS() {
    if (hljsLoaded || hljsLoading) return;
    hljsLoading = true;
    
    try {
        // Load CSS
        const link = document.createElement('link');
        link.rel = 'stylesheet';
        link.href = '/vendor/highlight/github-dark.min.css';
        document.head.appendChild(link);
        
        // Load core
        await loadScript('/vendor/highlight/highlight.min.js');
        
        // Load common languages in parallel
        await Promise.all([
            loadScript('/vendor/highlight/languages/python.min.js'),
            loadScript('/vendor/highlight/languages/javascript.min.js'),
            loadScript('/vendor/highlight/languages/bash.min.js'),
            loadScript('/vendor/highlight/languages/json.min.js')
        ]);
        
        hljsLoaded = true;
        
        // Re-highlight any existing code blocks
        document.querySelectorAll('pre code:not(.hljs)').forEach(block => {
            hljs.highlightElement(block);
        });
    } catch (e) {
        console.warn('Failed to load highlight.js:', e);
    }
    hljsLoading = false;
}

function loadScript(src) {
    return new Promise((resolve, reject) => {
        const script = document.createElement('script');
        script.src = src;
        script.onload = resolve;
        script.onerror = reject;
        document.head.appendChild(script);
    });
}

// i18n translations
const i18n = {
    en: {
        newChat: 'New Chat',
        clearAllChats: 'Clear All',
        confirmClearAll: 'Are you sure you want to delete all chats? This cannot be undone.',
        allChatsCleared: 'All chats cleared',
        settings: 'Settings',
        delete: 'Delete',
        expand: 'Expand',
        collapse: 'Collapse',
        defaultSubtitle: 'Minimalist AI Assistant, Ready to Use',
        fastResponse: 'Fast Response',
        multiModel: 'Multi-Model',
        knowledgeBase: 'Knowledge Base',
        kbEnabled: 'KB Enabled',
        thinkingMode: 'Thinking Mode',
        thinkingEnabled: 'Thinking Enabled',
        thinkingProcess: 'Thinking Process',
        uploadImage: 'Upload Image',
        uploadDocument: 'Upload Document',
        image: 'Image',
        imageSelected: 'Image Selected',
        documentAttached: 'Document Attached',
        parseUrl: 'Parse URL',
        enterUrl: 'Enter URL',
        parsing: 'Parsing...',
        urlAttached: 'URL Attached',
        parseFailed: 'Parse failed',
        urlPlaceholder: 'https://example.com/article',
        confirm: 'OK',
        ragReferences: 'References',
        relevance: 'Relevance',
        copyMessage: 'Copy',
        copied: 'Copied!',
        inputPlaceholder: 'Type a message... (Enter to send, Shift+Enter for new line)',
        modelConfig: 'Models',
        chatSettings: 'Chat',
        chatSettingsDesc: 'Adjust how the AI responds to your inputs.',
        ragSettings: 'RAG',
        ragSettingsDesc: 'Configure retrieval augmented generation parameters.',
        uiSettings: 'Interface',
        uiSettingsDesc: 'Customize the interface appearance.',
        kbDesc: 'Upload documents for RAG context.',
        modelConfigDesc: 'Manage your AI model connections and parameters.',
        modelType: 'Type',
        chat: 'Chat',
        embedding: 'Embedding',
        reranker: 'Reranker',
        optional: 'Optional',
        contextLength: 'Context Length',
        maxOutput: 'Max Output',
        capabilities: 'Capabilities',
        vision: 'Vision',
        reasoning: 'Reasoning',
        tools: 'Tools',
        saveAndVerify: 'Save & Verify',
        verifying: 'Verifying...',
        verifySuccess: 'Connected',
        verifyFailed: 'Connection failed',
        temperatureHint: 'Lower values make output more deterministic, higher values more creative',
        topPHint: 'Nucleus sampling parameter, controls output diversity',
        streamOutput: 'Stream Output',
        streamHint: 'Display AI response in real-time',
        systemPrompt: 'System Prompt',
        systemPromptHint: 'Set instructions for the AI assistant',
        systemPromptPlaceholder: 'You are a helpful assistant...',
        chunkSize: 'Chunk Size',
        chunkSizeHint: 'Number of characters per document chunk',
        chunkOverlap: 'Chunk Overlap',
        chunkOverlapHint: 'Overlap characters between adjacent chunks',
        topKHint: 'Number of relevant documents to retrieve',
        scoreThreshold: 'Score Threshold',
        scoreThresholdHint: 'Documents below this threshold will be filtered',
        language: 'Language',
        theme: 'Theme',
        light: 'Light',
        dark: 'Dark',
        uploadLogo: 'Upload',
        logoText: 'Logo Text',
        subtitle: 'Subtitle',
        avatars: 'Avatars',
        userAvatar: 'User',
        aiAvatar: 'AI',
        uploadDocument: 'Upload Document',
        noDocuments: 'No documents yet. Upload one above.',
        cancel: 'Cancel',
        save: 'Save',
        uploadSuccess: 'uploaded successfully',
        uploadFailed: 'Upload failed',
        deleteFailed: 'Delete failed',
        saveFailed: 'Save failed',
        settingsSaved: 'Settings saved',
        sendFailed: 'Send failed',
        stopGeneration: 'Stop',
        createChatFailed: 'Failed to create chat',
        documentDeleted: 'Document deleted',
        logoName: 'Logo & Name',
        uploadUserAvatar: 'Upload User Avatar',
        uploadAIAvatar: 'Upload AI Avatar',
        active: 'Active',
        error: 'Error',
        mitLicense: 'MIT License',
        // Plugin translations
        plugins: 'Plugins',
        pluginMarket: 'Plugin Market',
        pluginMarketDesc: 'Browse and install plugins from the official market.',
        installedPlugins: 'Installed',
        installedPluginsDesc: 'Manage your installed plugins.',
        installLocalPlugin: 'Install Local',
        installLocalPluginDesc: 'Upload a plugin zip file to install.',
        refreshingMarket: 'Refreshing plugin market...',
        networkError: 'Please check network connection',
        retry: 'Retry',
        install: 'Install',
        installed: 'Installed',
        installing: 'Installing...',
        installSuccess: 'Plugin installed successfully',
        installFailed: 'Install failed',
        uninstall: 'Uninstall',
        uninstallSuccess: 'Plugin uninstalled',
        uninstallFailed: 'Uninstall failed',
        confirmUninstall: 'Are you sure you want to uninstall this plugin?',
        pluginDisabled: 'Plugin disabled',
        selectPluginZip: 'Click or drag to upload plugin (.zip)',
        pluginDevGuide: 'Plugin Development Guide',
        noPluginsAvailable: 'No plugins available',
        searchPlugins: 'Search plugins',
        noPluginsInstalled: 'No plugins installed yet',
        noPluginSettings: 'This plugin has no settings.',
        apiKeySettings: 'API Key Settings',
        enterApiKey: 'Enter API Key',
        apiKeySet: 'API Key is already set. Clear and enter new key to change.',
        onlyZipSupported: 'Only .zip files are supported',
        hermesRun: 'Hermes Run',
        hermesRunStatusStarted: 'Started',
        hermesRunStatusRunning: 'Running',
        hermesRunStatusPendingApproval: 'Pending approval',
        hermesRunStatusCompleted: 'Completed',
        hermesRunStatusFailed: 'Failed',
        hermesRunStatusCancelled: 'Cancelled',
        hermesRunEventRunStarted: 'Run started',
        hermesRunEventToolStarted: 'Tool started',
        hermesRunEventToolCompleted: 'Tool completed',
        hermesRunEventReasoning: 'Reasoning available',
        hermesRunEventApprovalRequest: 'Approval required',
        hermesRunEventApprovalResponded: 'Approval responded',
        hermesRunEventRunCompleted: 'Run completed',
        hermesRunEventRunFailed: 'Run failed',
        hermesRunEventRunCancelled: 'Run cancelled',
        hermesRunTool: 'Tool',
        hermesRunPreview: 'Preview',
        hermesRunCommand: 'Command',
        hermesRunDescription: 'Description',
        hermesRunPatterns: 'Patterns',
        hermesRunDuration: 'Duration',
        hermesRunChoice: 'Choice',
        hermesApprovalOnce: 'Allow once',
        hermesApprovalSession: 'Allow for session',
        hermesApprovalDeny: 'Deny',
        hermesApprovalSubmitting: 'Submitting...',
        hermesApprovalError: 'Approval failed',
        close: 'Close'
    },
    zh: {
        newChat: '新对话',
        clearAllChats: '清空所有',
        confirmClearAll: '确定要删除所有对话吗？此操作无法撤销。',
        allChatsCleared: '已清空所有对话',
        settings: '设置',
        delete: '删除',
        expand: '展开',
        collapse: '收起',
        defaultSubtitle: '极简AI助手，开箱即用',
        fastResponse: '极速响应',
        multiModel: '多模型支持',
        knowledgeBase: '知识库',
        kbEnabled: '知识库已开启',
        thinkingMode: '思考模式',
        thinkingEnabled: '思考模式已开启',
        thinkingProcess: '思考过程',
        uploadImage: '上传图片',
        uploadDocument: '上传文档',
        image: '图片',
        imageSelected: '已选择图片',
        documentAttached: '已附加文档',
        parseUrl: '解析网页',
        enterUrl: '输入网址',
        parsing: '解析中...',
        urlAttached: '已附加网页',
        parseFailed: '解析失败',
        urlPlaceholder: 'https://example.com/article',
        confirm: '确定',
        ragReferences: '引用来源',
        relevance: '相关度',
        copyMessage: '复制',
        copied: '已复制',
        inputPlaceholder: '输入消息... (Enter 发送, Shift+Enter 换行)',
        modelConfig: '模型配置',
        modelConfigDesc: '管理您的AI模型连接和参数',
        chatSettings: '聊天设置',
        chatSettingsDesc: '调整AI对您输入的响应方式',
        ragSettings: 'RAG设置',
        ragSettingsDesc: '配置检索增强生成 (RAG) 参数',
        uiSettings: '界面设置',
        uiSettingsDesc: '自定义界面外观',
        kbDesc: '上传用于RAG上下文的文档',
        modelType: '类型',
        chat: '聊天',
        embedding: '嵌入',
        reranker: '重排',
        optional: '可选',
        contextLength: '上下文长度',
        maxOutput: '最大输出',
        capabilities: '模型能力',
        vision: '视觉',
        reasoning: '推理',
        tools: '工具',
        saveAndVerify: '保存并验证',
        verifying: '验证中...',
        verifySuccess: '连接成功',
        verifyFailed: '连接失败',
        temperatureHint: '较低的值使输出更确定，较高的值更有创意',
        topPHint: '核采样参数，控制输出的多样性',
        streamOutput: '流式输出',
        streamHint: '实时显示AI的回复内容',
        systemPrompt: '系统提示词',
        systemPromptHint: '设置AI助手的行为指令',
        systemPromptPlaceholder: '你是一个有帮助的助手...',
        chunkSize: '文档块大小',
        chunkSizeHint: '文档分块的字符数',
        chunkOverlap: '块重叠',
        chunkOverlapHint: '相邻块之间的重叠字符数',
        topKHint: '检索相关文档的数量',
        scoreThreshold: '相似度阈值',
        scoreThresholdHint: '低于此阈值的文档将被过滤',
        language: '语言',
        theme: '主题',
        light: '浅色',
        dark: '深色',
        uploadLogo: '上传',
        logoText: 'Logo文字',
        subtitle: '副标题',
        avatars: '头像',
        userAvatar: '用户',
        aiAvatar: 'AI',
        uploadDocument: '上传文档',
        noDocuments: '暂无文档，请在上方上传',
        cancel: '取消',
        save: '保存',
        uploadSuccess: '上传成功',
        uploadFailed: '上传失败',
        deleteFailed: '删除失败',
        saveFailed: '保存失败',
        settingsSaved: '设置已保存',
        sendFailed: '发送失败',
        stopGeneration: '停止',
        createChatFailed: '创建对话失败',
        documentDeleted: '文档已删除',
        logoName: 'Logo & 名称',
        uploadUserAvatar: '上传用户头像',
        uploadAIAvatar: '上传 AI 头像',
        active: '活跃',
        error: '错误',
        mitLicense: 'MIT 协议',
        // Plugin translations
        plugins: '插件',
        pluginMarket: '插件市场',
        pluginMarketDesc: '浏览并安装官方市场的插件',
        installedPlugins: '已安装',
        installedPluginsDesc: '管理已安装的插件',
        installLocalPlugin: '本地安装',
        installLocalPluginDesc: '上传插件 zip 文件进行安装',
        refreshingMarket: '正在刷新插件市场...',
        networkError: '请检查网络连接',
        retry: '重试',
        install: '安装',
        installed: '已安装',
        installing: '安装中...',
        installSuccess: '插件安装成功',
        installFailed: '安装失败',
        uninstall: '卸载',
        uninstallSuccess: '插件已卸载',
        uninstallFailed: '卸载失败',
        confirmUninstall: '确定要卸载此插件吗？',
        pluginDisabled: '插件已禁用',
        selectPluginZip: '点击或拖拽上传插件 (.zip)',
        pluginDevGuide: '插件开发指南',
        noPluginsAvailable: '暂无可用插件',
        searchPlugins: '搜索插件',
        noPluginsInstalled: '暂未安装任何插件',
        noPluginSettings: '此插件暂无可配置项',
        apiKeySettings: 'API 密钥设置',
        enterApiKey: '输入 API Key',
        apiKeySet: 'API Key 已设置。清空后输入新密钥可更改。',
        onlyZipSupported: '仅支持 .zip 文件',
        hermesRun: 'Hermes Run',
        hermesRunStatusStarted: '已开始',
        hermesRunStatusRunning: '运行中',
        hermesRunStatusPendingApproval: '等待审批',
        hermesRunStatusCompleted: '已完成',
        hermesRunStatusFailed: '失败',
        hermesRunStatusCancelled: '已取消',
        hermesRunEventRunStarted: 'Run 已开始',
        hermesRunEventToolStarted: '工具已启动',
        hermesRunEventToolCompleted: '工具已完成',
        hermesRunEventReasoning: '推理可用',
        hermesRunEventApprovalRequest: '需要审批',
        hermesRunEventApprovalResponded: '审批已响应',
        hermesRunEventRunCompleted: 'Run 已完成',
        hermesRunEventRunFailed: 'Run 失败',
        hermesRunEventRunCancelled: 'Run 已取消',
        hermesRunTool: '工具',
        hermesRunPreview: '预览',
        hermesRunCommand: '命令',
        hermesRunDescription: '说明',
        hermesRunPatterns: '规则',
        hermesRunDuration: '耗时',
        hermesRunChoice: '选择',
        hermesApprovalOnce: '允许一次',
        hermesApprovalSession: '本会话允许',
        hermesApprovalDeny: '拒绝',
        hermesApprovalSubmitting: '提交中...',
        hermesApprovalError: '审批失败',
        close: '关闭'
    }
};

// Configure marked.js with lazy-loaded highlight.js
marked.setOptions({
    highlight: function(code, lang) {
        // Trigger lazy load of highlight.js
        if (!hljsLoaded && !hljsLoading) {
            loadHighlightJS();
        }
        
        // If hljs is available, use it
        if (typeof hljs !== 'undefined') {
            if (lang && hljs.getLanguage(lang)) {
                try {
                    return hljs.highlight(code, { language: lang }).value;
                } catch (e) {}
            }
            return hljs.highlightAuto(code).value;
        }
        
        // Return escaped code if hljs not loaded yet
        return code.replace(/</g, '&lt;').replace(/>/g, '&gt;');
    },
    breaks: true,
    gfm: true
});

const MOBILE_VIEW_MEDIA_QUERY = '(max-width: 768px), (max-height: 500px) and (max-width: 900px) and (pointer: coarse)';

function isMobileViewport() {
    return window.matchMedia(MOBILE_VIEW_MEDIA_QUERY).matches;
}

const SKILL_MANAGER_PLUGIN_ID = 'skill-manager';
const COMPOSER_COMPLETION_LIMIT = 20;
const SKILL_CATALOG_CACHE_MS = 30000;
const MAX_ACTIVE_SKILLS_PER_REQUEST = 5;
const DEFAULT_CHAT_ENDPOINT = '/api/chat';
const CHAT_ROUTE_ENDPOINTS = Object.freeze({
    hermes: '/api/hermes/chat'
});
const ALLOWED_CHAT_ENDPOINTS = new Set([DEFAULT_CHAT_ENDPOINT, ...Object.values(CHAT_ROUTE_ENDPOINTS)]);
const ROUTE_MESSAGE_RESULT_KEYS = new Set(['success', 'route']);
const RESERVED_SLASH_COMMANDS = new Set(['plugins', 'settings', 'help', 'clear', 'compact', 'api']);
const COMMON_PATH_ROOTS = new Set(['tmp', 'var', 'usr', 'etc', 'home', 'users', 'opt', 'private', 'volumes', 'mnt']);
const SKILL_NAME_PATTERN = /^[a-z0-9](?:[a-z0-9-]{0,62}[a-z0-9])?$/;
const MODULE_SDK_VERSION = '1.0.0';
const MODULE_TASK_STORAGE_KEY = 'chatraw_module_tasks_v1';
const MODULE_TERMINAL_STATES = new Set(['succeeded', 'failed', 'cancelled']);

function app() {
    const initialDesktopCollapsed = localStorage.getItem('chatraw_sidebar_collapsed') === '1';
    const initialIsMobile = isMobileViewport();
    
    return {
        // Language
        lang: localStorage.getItem('justchat_lang') || 'en',
        
        // State
        isMobileView: initialIsMobile,
        desktopSidebarCollapsed: initialDesktopCollapsed,
        sidebarCollapsed: initialIsMobile ? true : initialDesktopCollapsed,
        _resizeRaf: null,
        showSettings: false,
        settingsTab: 'models',
        me: null,
        adminUsers: [],
        newUser: { username: '', password: '', role: 'member' },
        passwordForm: { current_password: '', new_password: '' },
        modules: [],
        modulePairForm: { base_url: '', pairing_code: '' },
        deploymentStatus: {
            mode: 'source',
            module_network: null,
            warnings: []
        },
        moduleBusy: null,
        moduleConfig: null,
        moduleConfigValues: {},
        moduleSecretActions: {},
        moduleTaskUi: {
            show: false,
            task: null,
            events: [],
            output: '',
            progress: 0,
            progressMessage: '',
            approval: null,
            artifacts: [],
            error: null
        },
        moduleTasks: {},
        moduleTaskOrder: [],
        moduleTaskSubscriptions: {},
        showSystemPrompt: false,
        currentChatId: null,
        inputMessage: '',
        isComposing: false,
        completionProviders: {},
        completionMenuOpen: false,
        completionQuery: '',
        completionItems: [],
        completionActiveIndex: 0,
        completionRange: null,
        completionRequestId: 0,
        completionDebounceTimer: null,
        skillCatalogCache: null,
        skillCatalogLoadedAt: 0,
        useRAG: false,
        useThinking: false,
        isGenerating: false,
        abortController: null,
        uploadedImage: null,
        uploadedImageBase64: '',
        uploadProgress: { show: false, filename: '', progress: 0, status: '', current: 0, total: 0 },
        
        // URL Parser state
        showUrlInput: false,
        urlInputValue: '',
        isParsingUrl: false,
        parsedUrl: null,  // { title, content, url }
        parsedUrlTitle: '',
        
        // Document attachment state
        attachedDocument: null,  // { filename, content }
        isUploadingDocument: false,
        
        // Plugin state
        showPlugins: false,
        pluginTab: 'market',
        marketPlugins: [],
        installedPlugins: [],
        pluginMarketLoading: false,
        pluginMarketError: false,
        pluginMarketSearch: '',
        pluginInstalling: null,
        pluginUploading: false,
        showPluginSettings: false,
        currentPluginSettings: null,
        pluginSettingsValues: {},
        pluginApiKeys: {},
        pluginApiKeyConfigured: {},
        pluginApiKeyActions: {},
        
        // Plugin toolbar extension state
        pluginToolbarButtons: [],  // [{fullId, pluginId, id, icon, label, onClick, order, active, loading}]
        showPluginMoreMenu: false,
        pluginFullscreenModal: {
            show: false,
            content: '',
            closable: true,
            onClose: null,
            pluginId: null
        },
        
        // Plugin hooks system
        pluginHooks: {
            // Document/Content processing
            parse_document: [],      // Parse uploaded documents
            parse_url: [],           // Parse web URL (url_parser plugins)
            web_search: [],          // Web search providers
            pre_embedding: [],       // Before embedding text
            post_retrieval: [],      // After RAG retrieval
            
            // Message lifecycle
            send_intercept: [],      // Pre-send interceptors that can fully handle a message
            before_send: [],         // Before sending message to AI
            route_message: [],        // Select a host-approved chat route
            after_receive: [],       // After receiving AI response
            
            // UI extensions
            toolbar_button: [],      // Add toolbar buttons
            file_preview: [],        // Custom file preview renderers
            custom_action: [],       // Custom action handlers
            custom_settings: [],     // Custom settings UI
            
            // Content transformation
            transform_input: [],     // Transform user input
            transform_output: [],    // Transform AI output before display
        },
        loadedPluginDeps: {},
        
        // Data
        chats: [],
        messages: [],
        models: [],
        documents: [],
        settings: {
            chat_settings: {
                temperature: 0.7,
                top_p: 0.9,
                stream: true,
                system_prompt: ''
            },
            rag_settings: {
                chunk_size: 500,
                chunk_overlap: 50,
                top_k: 3,
                score_threshold: 0.5
            },
            ui_settings: {
                logo_data: '',
                logo_text: 'ChatRaw',
                subtitle: '',
                theme_mode: 'light',
                user_avatar: '',
                assistant_avatar: ''
            }
        },
        
        // Toast
        toast: {
            show: false,
            message: '',
            type: ''
        },
        
        // Translation helper
        t(key) {
            return i18n[this.lang][key] || key;
        },
        
        // Set language
        setLanguage(newLang) {
            this.lang = newLang;
            localStorage.setItem('justchat_lang', newLang);
        },
        
        // Get model type display name
        getModelTypeName(type) {
            const names = {
                chat: this.t('chat'),
                embedding: this.t('embedding'),
                rerank: this.t('reranker')
            };
            return names[type] || type;
        },
        
        getChatModel() {
            return this.models.find(model => model?.type === 'chat') || null;
        },

        chatModelSupportsVision() {
            return Boolean(this.getChatModel()?.capability?.vision);
        },

        syncVisionCapabilityState() {
            if (!this.chatModelSupportsVision() && this.uploadedImage) {
                this.removeUploadedImage();
            }
        },

        // Initialize
        async init() {
            this.initResponsiveLayout();
            await this.loadMe();
            await this.loadSettings();
            await this.loadModels();
            await this.loadChats();
            await this.loadDocuments();
            await this.loadInstalledPlugins();
            this.applyTheme();
            // Note: favicon is updated by loadLogo() which is called from loadSettings()
            // Initialize plugin system
            this.initPluginSystem();
            await this.resumeModuleTasks();
        },

        isAdmin() {
            return this.me?.role === 'admin';
        },

        async loadMe() {
            const response = await fetch('/api/me');
            if (!response.ok) {
                location.replace('/login');
                throw new Error('Authentication required');
            }
            this.me = await response.json();
            if (!this.isAdmin()) this.settingsTab = 'account';
        },

        async logout() {
            await fetch('/api/auth/logout', { method: 'POST' });
            location.replace('/login');
        },

        async loadAdminUsers() {
            if (!this.isAdmin()) return;
            const response = await fetch('/api/admin/users');
            if (response.ok) {
                const data = await response.json();
                this.adminUsers = data.users || [];
            }
        },

        async createManagedUser() {
            const response = await fetch('/api/admin/users', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(this.newUser)
            });
            const result = await response.json();
            if (!response.ok) {
                this.showToast(result.detail || 'Unable to create user', 'error');
                return;
            }
            this.newUser = { username: '', password: '', role: 'member' };
            await this.loadAdminUsers();
            this.showToast('User created', 'success');
        },

        async setManagedUserEnabled(user, enabled) {
            const action = enabled ? 'enable' : 'disable';
            const response = await fetch(`/api/admin/users/${encodeURIComponent(user.id)}/${action}`, {
                method: 'POST'
            });
            const result = await response.json();
            if (!response.ok) {
                this.showToast(result.detail || 'Unable to update user', 'error');
                return;
            }
            await this.loadAdminUsers();
        },

        async resetManagedUserPassword(user) {
            const newPassword = window.prompt(`New password for ${user.username}`);
            if (!newPassword) return;
            const response = await fetch(`/api/admin/users/${encodeURIComponent(user.id)}/reset-password`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ new_password: newPassword })
            });
            const result = await response.json();
            if (!response.ok) {
                this.showToast(result.detail || 'Unable to reset password', 'error');
                return;
            }
            this.showToast('Password reset; existing sessions revoked', 'success');
        },

        async changeMyPassword() {
            const response = await fetch('/api/me/password', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(this.passwordForm)
            });
            const result = await response.json();
            if (!response.ok) {
                this.showToast(result.detail || 'Unable to change password', 'error');
                return;
            }
            location.replace('/login');
        },

        async moduleApi(path, options = {}) {
            const response = await fetch(path, options);
            let result = {};
            try {
                result = await response.json();
            } catch (_error) {
                result = {};
            }
            if (!response.ok) {
                throw new Error(result.detail || 'Module operation failed');
            }
            return result;
        },

        moduleTaskIds() {
            try {
                const value = JSON.parse(
                    localStorage.getItem(MODULE_TASK_STORAGE_KEY) || '[]'
                );
                return Array.isArray(value)
                    ? value.filter(item => typeof item === 'string').slice(0, 20)
                    : [];
            } catch (_error) {
                return [];
            }
        },

        rememberModuleTask(taskId) {
            const taskIds = [
                taskId,
                ...this.moduleTaskIds().filter(item => item !== taskId)
            ].slice(0, 20);
            localStorage.setItem(
                MODULE_TASK_STORAGE_KEY,
                JSON.stringify(taskIds)
            );
        },

        forgetModuleTask(taskId) {
            localStorage.setItem(
                MODULE_TASK_STORAGE_KEY,
                JSON.stringify(
                    this.moduleTaskIds().filter(item => item !== taskId)
                )
            );
        },

        createModuleTaskView(task) {
            return {
                show: false,
                task,
                events: [],
                output: task?.result?.text || task?.chat_projection || '',
                progress: MODULE_TERMINAL_STATES.has(task?.state) ? 1 : 0,
                progressMessage: '',
                approval: null,
                artifacts: Array.isArray(task?.artifacts) ? task.artifacts : [],
                error: task?.state === 'failed'
                    ? (task.outcome_code || 'Task failed')
                    : null
            };
        },

        upsertModuleTask(task, { select = false } = {}) {
            const taskId = task?.task_id;
            if (!taskId) return null;
            let view = this.moduleTasks[taskId];
            if (!view) {
                view = this.createModuleTaskView(task);
                this.moduleTasks[taskId] = view;
                this.moduleTaskOrder = [
                    taskId,
                    ...this.moduleTaskOrder.filter(item => item !== taskId)
                ].slice(0, 20);
            } else {
                view.task = task;
                view.artifacts = Array.isArray(task.artifacts)
                    ? task.artifacts
                    : view.artifacts;
                if (MODULE_TERMINAL_STATES.has(task.state)) {
                    view.progress = 1;
                    view.approval = null;
                    view.error = task.state === 'failed'
                        ? (task.outcome_code || 'Task failed')
                        : null;
                }
            }
            if (select) this.selectModuleTask(taskId);
            return view;
        },

        moduleTaskViews() {
            return this.moduleTaskOrder
                .map(taskId => this.moduleTasks[taskId])
                .filter(Boolean);
        },

        selectModuleTask(taskId) {
            const view = this.moduleTasks[taskId];
            if (!view) return;
            this.moduleTaskUi.show = false;
            view.show = true;
            this.moduleTaskUi = view;
        },

        showModuleTask(task) {
            this.upsertModuleTask(task, { select: true });
        },

        openModuleTaskCenter() {
            const first = this.moduleTaskUi.task?.task_id
                || this.moduleTaskOrder[0];
            if (first) this.selectModuleTask(first);
        },

        closeModuleTask() {
            this.moduleTaskUi.show = false;
        },

        applyModuleTaskEvent(taskId, event) {
            const ui = this.moduleTasks[taskId];
            if (!ui) return;
            ui.events.push(event);
            if (ui.events.length > 200) ui.events.shift();
            if (event.event === 'task.status' || event.event === 'task.terminal') {
                ui.task.state = event.data.state;
                if (event.data.outcome_code) {
                    ui.task.outcome_code = event.data.outcome_code;
                }
                if (event.event === 'task.terminal') {
                    ui.progress = 1;
                    if (event.data.state === 'failed') {
                        ui.error = event.data.outcome_code || 'Task failed';
                    }
                    ui.approval = null;
                }
            } else if (event.event === 'task.progress') {
                ui.progress = event.data.progress;
                ui.progressMessage = event.data.message || '';
            } else if (event.event === 'output.delta') {
                ui.output += event.data.text;
            } else if (event.event === 'output.snapshot') {
                ui.output = event.data.text;
            } else if (event.event === 'approval.requested') {
                ui.approval = event.data;
            } else if (event.event === 'approval.resolved') {
                ui.approval = null;
            }
        },

        async resolveModuleTaskApproval(decision) {
            const task = this.moduleTaskUi.task;
            const approval = this.moduleTaskUi.approval;
            if (!task || !approval) return;
            try {
                await window.ChatRaw.modules.respondApproval(
                    task.task_id,
                    approval.approval_id,
                    decision
                );
            } catch (error) {
                this.moduleTaskUi.error = error.message;
            }
        },

        async cancelVisibleModuleTask() {
            const taskId = this.moduleTaskUi.task?.task_id;
            if (!taskId) return;
            try {
                const task = await window.ChatRaw.modules.cancelTask(taskId);
                this.upsertModuleTask(task);
            } catch (error) {
                this.moduleTaskUi.error = error.message;
            }
        },

        async downloadVisibleModuleArtifact(artifact) {
            const taskId = this.moduleTaskUi.task?.task_id;
            if (!taskId) return;
            try {
                await window.ChatRaw.modules.downloadArtifact(
                    taskId,
                    artifact.artifact_ref
                );
            } catch (error) {
                this.moduleTaskUi.error = error.message;
            }
        },

        async resumeModuleTasks() {
            if (!window.ChatRaw?.modules) return;
            let firstActive = null;
            for (const taskId of this.moduleTaskIds()) {
                try {
                    const task = await window.ChatRaw.modules.getTask(taskId);
                    this.upsertModuleTask(task);
                    if (!MODULE_TERMINAL_STATES.has(task.state)) {
                        if (!firstActive) firstActive = taskId;
                        window.ChatRaw.modules.subscribe(taskId);
                    }
                } catch (error) {
                    if (error?.status === 404) this.forgetModuleTask(taskId);
                }
            }
            if (firstActive) this.selectModuleTask(firstActive);
        },

        async loadModules() {
            if (!this.isAdmin()) return;
            try {
                const [data, deployment] = await Promise.all([
                    this.moduleApi('/api/admin/modules'),
                    this.moduleApi('/api/admin/deployment-status')
                ]);
                this.modules = data.modules || [];
                this.deploymentStatus = deployment;
            } catch (error) {
                this.showToast(error.message, 'error');
            }
        },

        async pairModule() {
            if (!this.isAdmin() || this.moduleBusy) return;
            this.moduleBusy = 'pair';
            try {
                await this.moduleApi('/api/admin/modules/pair', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(this.modulePairForm)
                });
                this.modulePairForm = { base_url: '', pairing_code: '' };
                await this.loadModules();
                this.showToast('Module paired for review', 'success');
            } catch (error) {
                this.showToast(error.message, 'error');
            } finally {
                this.moduleBusy = null;
            }
        },

        async approveModule(module) {
            if (!this.isAdmin() || this.moduleBusy) return;
            if (!window.confirm(`Approve ${module.module_id} and its declared capabilities?`)) return;
            this.moduleBusy = module.id;
            try {
                await this.moduleApi(`/api/admin/modules/${encodeURIComponent(module.id)}/approve`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        manifest_digest: module.manifest_digest,
                        approved_capabilities: module.requested_host_capabilities || []
                    })
                });
                await this.loadModules();
                this.showToast('Module manifest approved', 'success');
            } catch (error) {
                this.showToast(error.message, 'error');
            } finally {
                this.moduleBusy = null;
            }
        },

        async runModuleAction(module, action) {
            if (!this.isAdmin() || this.moduleBusy) return;
            this.moduleBusy = module.id;
            try {
                await this.moduleApi(`/api/admin/modules/${encodeURIComponent(module.id)}/${action}`, {
                    method: 'POST'
                });
                await this.loadModules();
                this.showToast(`Module ${action} completed`, 'success');
            } catch (error) {
                this.showToast(error.message, 'error');
            } finally {
                this.moduleBusy = null;
            }
        },

        moduleConfigFields() {
            return Object.entries(this.moduleConfig?.schema?.properties || {}).map(([name, schema]) => ({
                name,
                schema,
                secret: schema?.['x-chatraw-secret'] === true
            }));
        },

        async openModuleConfig(module) {
            if (!this.isAdmin()) return;
            this.moduleBusy = module.id;
            try {
                const config = await this.moduleApi(`/api/admin/modules/${encodeURIComponent(module.id)}/config`);
                this.moduleConfig = { ...config, moduleId: module.id, moduleName: module.name };
                this.moduleConfigValues = { ...(config.values || {}) };
                this.moduleSecretActions = {};
                for (const field of Object.entries(config.schema?.properties || {})) {
                    if (field[1]?.['x-chatraw-secret'] === true) {
                        this.moduleSecretActions[field[0]] = {
                            action: 'keep',
                            value: ''
                        };
                    } else if (this.moduleConfigValues[field[0]] === undefined && field[1]?.default !== undefined) {
                        this.moduleConfigValues[field[0]] = field[1].default;
                    }
                }
            } catch (error) {
                this.showToast(error.message, 'error');
            } finally {
                this.moduleBusy = null;
            }
        },

        async saveModuleConfig() {
            if (!this.isAdmin() || !this.moduleConfig || this.moduleBusy) return;
            this.moduleBusy = this.moduleConfig.moduleId;
            const secrets = {};
            for (const [name, update] of Object.entries(this.moduleSecretActions)) {
                secrets[name] = update.action === 'replace'
                    ? { action: 'replace', value: update.value }
                    : { action: update.action };
            }
            try {
                const config = await this.moduleApi(`/api/admin/modules/${encodeURIComponent(this.moduleConfig.moduleId)}/config`, {
                    method: 'PUT',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        revision: this.moduleConfig.revision,
                        values: this.moduleConfigValues,
                        secrets
                    })
                });
                this.moduleConfig = null;
                await this.loadModules();
                this.showToast(`Configuration saved at revision ${config.revision}`, 'success');
            } catch (error) {
                this.showToast(error.message, 'error');
            } finally {
                this.moduleBusy = null;
            }
        },

        async disconnectModule(module) {
            if (!this.isAdmin() || this.moduleBusy) return;
            const confirmation = window.prompt(`Type ${module.module_id} to disconnect. Module data will be preserved.`);
            if (confirmation !== module.module_id) return;
            this.moduleBusy = module.id;
            try {
                await this.moduleApi(`/api/admin/modules/${encodeURIComponent(module.id)}/disconnect`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ confirmation })
                });
                await this.loadModules();
                this.showToast('Module disconnected; module data was preserved', 'success');
            } catch (error) {
                this.showToast(error.message, 'error');
            } finally {
                this.moduleBusy = null;
            }
        },

        async purgeModuleData(module) {
            if (!this.isAdmin() || !module.supports_data_purge || this.moduleBusy) return;
            const expected = `PURGE ${module.module_id}`;
            const confirmation = window.prompt(`This deletes data owned by the module. Type ${expected} to continue.`);
            if (confirmation !== expected) return;
            this.moduleBusy = module.id;
            try {
                await this.moduleApi(`/api/admin/modules/${encodeURIComponent(module.id)}/purge-data`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ confirmation })
                });
                await this.loadModules();
                this.showToast('Module-owned data purged', 'success');
            } catch (error) {
                this.showToast(error.message, 'error');
            } finally {
                this.moduleBusy = null;
            }
        },
        
        // Responsive layout sync (mobile drawer + desktop collapse)
        initResponsiveLayout() {
            this.syncSidebarForViewport(true);
            const onViewportChange = () => {
                if (this._resizeRaf) {
                    cancelAnimationFrame(this._resizeRaf);
                }
                this._resizeRaf = requestAnimationFrame(() => {
                    this.syncSidebarForViewport(false);
                });
            };
            window.addEventListener('resize', onViewportChange, { passive: true });
            window.addEventListener('orientationchange', onViewportChange, { passive: true });
        },
        
        syncSidebarForViewport(isInitial) {
            const isMobileNow = isMobileViewport();
            const switchedToMobile = !this.isMobileView && isMobileNow;
            const switchedToDesktop = this.isMobileView && !isMobileNow;
            this.isMobileView = isMobileNow;
            
            if (isMobileNow && (isInitial || switchedToMobile)) {
                // Mobile: default closed drawer, open via top menu.
                this.sidebarCollapsed = true;
            } else if (!isMobileNow && (isInitial || switchedToDesktop)) {
                // Desktop: restore persisted collapse preference.
                this.sidebarCollapsed = this.desktopSidebarCollapsed;
            }
        },
        
        toggleSidebar() {
            this.sidebarCollapsed = !this.sidebarCollapsed;
            if (!this.isMobileView) {
                this.desktopSidebarCollapsed = this.sidebarCollapsed;
                localStorage.setItem('chatraw_sidebar_collapsed', this.sidebarCollapsed ? '1' : '0');
            }
        },
        
        openSidebar() {
            this.sidebarCollapsed = false;
        },
        
        closeSidebar() {
            this.sidebarCollapsed = true;
        },
        
        closeSidebarOnMobile() {
            if (this.isMobileView) {
                this.closeSidebar();
            }
        },
        
        openSettingsPanel() {
            this.showPlugins = false;
            this.settingsTab = this.isAdmin() ? 'models' : 'account';
            this.showSettings = true;
            if (this.isAdmin()) {
                this.loadAdminUsers();
                this.loadModules();
            }
            this.closeSidebarOnMobile();
        },
        
        openPluginsPanel() {
            if (!this.isAdmin()) return;
            this.showSettings = false;
            this.showPlugins = true;
            this.loadPluginMarket();
            this.closeSidebarOnMobile();
        },
        
        // Apply theme
        applyTheme() {
            document.documentElement.setAttribute('data-theme', this.settings.ui_settings.theme_mode);
        },
        
        // Load settings
        async loadSettings() {
            try {
                const res = await fetch('/api/settings');
                if (res.ok) {
                    const data = await res.json();
                    // Deep merge settings
                    if (data.chat_settings) {
                        this.settings.chat_settings = { ...this.settings.chat_settings, ...data.chat_settings };
                    }
                    if (data.rag_settings) {
                        this.settings.rag_settings = { ...this.settings.rag_settings, ...data.rag_settings };
                    }
                    if (data.ui_settings) {
                        this.settings.ui_settings = { ...this.settings.ui_settings, ...data.ui_settings };
                    }
                }
                // Lazy load logo after initial settings (for better LCP)
                this.loadLogo();
            } catch (e) {
                console.error('Failed to load settings:', e);
            }
        },
        
        // Lazy load logo separately for better performance
        async loadLogo() {
            try {
                const res = await fetch('/api/settings/logo');
                if (res.ok) {
                    const data = await res.json();
                    if (data.logo_data) {
                        this.settings.ui_settings.logo_data = data.logo_data;
                        this.updateFavicon(data.logo_data);
                    }
                }
            } catch (e) {
                // Logo loading is non-critical, fail silently
            }
        },
        
        // Load model configs
        async loadModels() {
            try {
                const res = await fetch('/api/models');
                if (res.ok) {
                    this.models = await res.json();
                    this.models.forEach(m => {
                        m.api_key = '';
                        m.api_key_action = 'preserve';
                        if (!m.capability) {
                            m.capability = { vision: false, reasoning: false, tools: false };
                        }
                    });
                    this.syncVisionCapabilityState();
                }
            } catch (e) {
                console.error('Failed to load models:', e);
            }
        },
        
        // Load chat list
        async loadChats() {
            try {
                const res = await fetch('/api/chats');
                if (res.ok) {
                    this.chats = await res.json() || [];
                }
            } catch (e) {
                console.error('Failed to load chats:', e);
            }
        },
        
        // Load documents
        async loadDocuments() {
            try {
                const res = await fetch('/api/documents');
                if (res.ok) {
                    this.documents = await res.json() || [];
                }
            } catch (e) {
                console.error('Failed to load documents:', e);
            }
        },
        
        // Create new chat
        async createNewChat() {
            // Stop any ongoing generation first
            if (this.isGenerating) {
                this.stopGeneration();
            }
            
            try {
                const res = await fetch('/api/chats', { method: 'POST' });
                if (res.ok) {
                    const chat = await res.json();
                    this.chats.unshift(chat);
                    this.selectChat(chat.id);
                    this.closeSidebarOnMobile();
                }
            } catch (e) {
                this.showToast(this.t('createChatFailed'), 'error');
            }
        },
        
        // Select chat
        async selectChat(chatId) {
            if (this.currentChatId === chatId) {
                this.closeSidebarOnMobile();
                return;
            }
            if (this.isGenerating) {
                this.stopGeneration();
            }
            this.currentChatId = chatId;
            await this.loadMessages(chatId);
            this.closeSidebarOnMobile();
        },
        
        // Load messages
        async loadMessages(chatId) {
            try {
                const res = await fetch(`/api/chats/${chatId}/messages`);
                if (res.ok) {
                    this.messages = await res.json() || [];
                    this.$nextTick(() => this.scrollToBottom());
                }
            } catch (e) {
                console.error('Failed to load messages:', e);
            }
        },
        
        // Delete chat
        async deleteChat(chatId) {
            if (!confirm('Delete this shared chat? Other users will lose access to it.')) return;
            try {
                if (this.currentChatId === chatId && this.isGenerating) {
                    this.stopGeneration();
                }
                const response = await fetch(`/api/chats/${chatId}`, { method: 'DELETE' });
                if (!response.ok) {
                    const result = await response.json();
                    throw new Error(result.detail || this.t('deleteFailed'));
                }
                this.chats = this.chats.filter(c => c.id !== chatId);
                if (this.currentChatId === chatId) {
                    this.currentChatId = null;
                    this.messages = [];
                }
            } catch (e) {
                this.showToast(this.t('deleteFailed'), 'error');
            }
        },

        async renameChat(chat) {
            const title = window.prompt('Rename this shared chat', chat.title);
            if (!title || title.trim() === chat.title) return;
            const response = await fetch(`/api/chats/${encodeURIComponent(chat.id)}`, {
                method: 'PATCH',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ title: title.trim() })
            });
            const result = await response.json();
            if (!response.ok) {
                this.showToast(result.detail || 'Rename failed', 'error');
                return;
            }
            chat.title = result.title;
        },
        
        // Clear all chats
        async clearAllChats() {
            if (!confirm(this.t('confirmClearAll'))) return;
            if (this.isGenerating) {
                this.stopGeneration();
            }
            
            try {
                // Delete all chats one by one
                for (const chat of this.chats) {
                    const response = await fetch(`/api/chats/${chat.id}`, { method: 'DELETE' });
                    if (!response.ok) throw new Error(this.t('deleteFailed'));
                }
                this.chats = [];
                this.currentChatId = null;
                this.messages = [];
                this.showToast(this.t('allChatsCleared'), 'success');
            } catch (e) {
                this.showToast(this.t('deleteFailed'), 'error');
            }
        },
        
        // Stop generation
        stopGeneration() {
            if (this.abortController) {
                this.markActiveHermesRunCancelled();
                this.abortController.abort();
                this.abortController = null;
                this.isGenerating = false;
            }
        },

        // ============ Composer Input and Completion ============

        getLocalizedText(value, fallback = '') {
            if (!value) return fallback;
            if (typeof value === 'string') return value;
            if (typeof value === 'object') {
                return value[this.lang] || value.en || value.zh || Object.values(value).find(Boolean) || fallback;
            }
            return String(value);
        },

        escapeComposerHtml(value) {
            return String(value || '')
                .replace(/&/g, '&amp;')
                .replace(/</g, '&lt;')
                .replace(/>/g, '&gt;')
                .replace(/"/g, '&quot;')
                .replace(/'/g, '&#39;');
        },

        getComposerSelection() {
            const el = this.$refs.inputBox;
            const fallback = (this.inputMessage || '').length;
            return {
                start: el ? el.selectionStart : fallback,
                end: el ? el.selectionEnd : fallback
            };
        },

        setComposerValue(value, selectionStart = null, selectionEnd = null) {
            this.inputMessage = value;
            this.$nextTick(() => {
                const el = this.$refs.inputBox;
                if (!el) return;
                el.value = value;
                if (Number.isInteger(selectionStart)) {
                    const end = Number.isInteger(selectionEnd) ? selectionEnd : selectionStart;
                    el.setSelectionRange(selectionStart, end);
                }
                el.dispatchEvent(new Event('input', { bubbles: true }));
                this.autoResize(el);
            });
        },

        replaceComposerRange(start, end, text) {
            const value = this.inputMessage || '';
            const safeStart = Math.max(0, Math.min(start, value.length));
            const safeEnd = Math.max(safeStart, Math.min(end, value.length));
            const nextValue = value.slice(0, safeStart) + text + value.slice(safeEnd);
            const cursor = safeStart + text.length;
            this.setComposerValue(nextValue, cursor, cursor);
            return true;
        },

        insertComposerText(text) {
            const selection = this.getComposerSelection();
            return this.replaceComposerRange(selection.start, selection.end, text);
        },

        focusComposer() {
            this.$nextTick(() => this.$refs.inputBox?.focus());
        },

        handleComposerInput(event) {
            this.inputMessage = event.target.value;
            this.autoResize(event.target);
            this.syncComposerHighlightScroll(event);
            if (!this.isComposing) {
                this.queueCompletionRefresh();
            }
        },

        syncComposerHighlightScroll(event = null) {
            const source = event?.target || this.$refs.inputBox;
            const highlight = this.$refs.composerHighlight;
            if (!source || !highlight) return;
            highlight.scrollTop = source.scrollTop;
            highlight.scrollLeft = source.scrollLeft;
        },

        deleteComposerSkillToken(key) {
            const selection = this.getComposerSelection();
            if (selection.start !== selection.end) return false;

            const value = this.inputMessage || '';
            const cursor = selection.start;
            const ranges = this.getComposerSkillTokenRanges(value, { knownOnly: true });
            for (const range of ranges) {
                let deleteStart = range.start;
                let deleteEnd = range.end;
                let shouldDelete = false;

                if (key === 'Backspace') {
                    shouldDelete = cursor > range.start && cursor <= range.end;
                    if (!shouldDelete && cursor === range.end + 1 && /[ \t]/.test(value[range.end] || '')) {
                        shouldDelete = true;
                        deleteEnd = range.end + 1;
                    }
                } else if (key === 'Delete') {
                    shouldDelete = cursor >= range.start && cursor < range.end;
                    if (!shouldDelete && cursor === range.start - 1 && /[ \t]/.test(value[cursor] || '')) {
                        shouldDelete = true;
                        deleteStart = cursor;
                    }
                }

                if (!shouldDelete) continue;
                if (/[ \t]/.test(value[range.end] || '')) {
                    deleteEnd = Math.max(deleteEnd, range.end + 1);
                }
                this.replaceComposerRange(deleteStart, deleteEnd, '');
                return true;
            }
            return false;
        },

        handleCompositionStart() {
            this.isComposing = true;
        },

        handleCompositionEnd(event) {
            this.isComposing = false;
            this.handleComposerInput(event);
        },

        async handleComposerKeydown(event) {
            if (this.isComposing || event.isComposing) return;

            if ((event.key === 'Backspace' || event.key === 'Delete') && this.deleteComposerSkillToken(event.key)) {
                event.preventDefault();
                this.closeCompletionMenu();
                return;
            }

            if (this.completionMenuOpen) {
                if (event.key === 'ArrowDown') {
                    event.preventDefault();
                    this.moveCompletionHighlight(1);
                    return;
                }
                if (event.key === 'ArrowUp') {
                    event.preventDefault();
                    this.moveCompletionHighlight(-1);
                    return;
                }
                if (event.key === 'Tab' || (event.key === 'Enter' && !event.shiftKey)) {
                    event.preventDefault();
                    await this.acceptHighlightedCompletion();
                    return;
                }
                if (event.key === 'Escape') {
                    event.preventDefault();
                    this.closeCompletionMenu();
                    return;
                }
            }

            if (event.key === 'Enter' && !event.shiftKey) {
                event.preventDefault();
                await this.sendMessage();
            }
        },

        moveCompletionHighlight(delta) {
            if (!this.completionItems.length) return;
            const length = this.completionItems.length;
            this.completionActiveIndex = (this.completionActiveIndex + delta + length) % length;
            this.scrollActiveCompletionIntoView();
        },

        scrollActiveCompletionIntoView() {
            this.$nextTick(() => {
                const menu = this.$refs.composerSuggestions;
                const activeItem = menu?.querySelector('.composer-suggestion-item.active');
                activeItem?.scrollIntoView({ block: 'nearest' });
            });
        },

        async acceptHighlightedCompletion() {
            const item = this.completionItems[this.completionActiveIndex];
            if (item) {
                await this.acceptCompletion(item);
            }
        },

        isCursorInFencedCode(value, cursor) {
            const before = value.slice(0, cursor);
            const matches = before.match(/```/g);
            return Boolean(matches && matches.length % 2 === 1);
        },

        isCursorInMarkdownLink(value, cursor) {
            const local = value.slice(Math.max(0, cursor - 160), cursor);
            const lastOpenBracket = local.lastIndexOf('[');
            const lastLinkStart = local.lastIndexOf('](');
            const lastCloseParen = local.lastIndexOf(')');
            return Math.max(lastOpenBracket, lastLinkStart) > lastCloseParen;
        },

        detectSlashToken(value, cursor) {
            if (!Number.isInteger(cursor)) return null;
            if (this.isCursorInFencedCode(value, cursor) || this.isCursorInMarkdownLink(value, cursor)) {
                return null;
            }

            const before = value.slice(0, cursor);
            const lineStart = before.lastIndexOf('\n') + 1;
            const linePrefix = before.slice(lineStart);
            const match = linePrefix.match(/(^|\s)(\/\S*)$/);
            if (!match) return null;

            const token = match[2];
            if (!/^\/[a-z0-9-]*$/.test(token)) return null;
            const query = token.slice(1);
            if (COMMON_PATH_ROOTS.has(query.toLowerCase())) return null;
            const start = lineStart + linePrefix.length - token.length;
            const end = cursor;
            return {
                start,
                end,
                query,
                trigger: '/'
            };
        },

        queueCompletionRefresh(delay = 80) {
            if (this.completionDebounceTimer) {
                clearTimeout(this.completionDebounceTimer);
            }
            this.completionDebounceTimer = setTimeout(() => {
                this.completionDebounceTimer = null;
                this.refreshCompletions();
            }, delay);
        },

        async refreshCompletions() {
            const el = this.$refs.inputBox;
            if (!el || this.isComposing) return;

            const range = this.detectSlashToken(this.inputMessage || '', el.selectionStart);
            if (!range) {
                this.closeCompletionMenu();
                return;
            }

            const requestId = ++this.completionRequestId;
            this.completionRange = range;
            this.completionQuery = range.query;

            const context = {
                trigger: range.trigger,
                query: range.query,
                range: { ...range },
                value: this.inputMessage || '',
                selection: this.getComposerSelection()
            };

            const providers = this.getActiveCompletionProviders(range.trigger);
            const items = [];
            for (const provider of providers) {
                try {
                    const providerItems = await Promise.resolve(provider.getItems(context));
                    if (requestId !== this.completionRequestId) return;
                    for (const item of providerItems || []) {
                        if (!item || !item.id || !item.label) continue;
                        items.push({
                            ...item,
                            providerId: provider.fullId,
                            pluginId: provider.pluginId,
                            source: item.source || provider.source || provider.pluginId,
                            icon: item.icon || provider.icon || 'ri-command-line'
                        });
                        if (items.length >= COMPOSER_COMPLETION_LIMIT) break;
                    }
                } catch (error) {
                    console.error(`[Completion ${provider.fullId}] Error:`, error);
                }
                if (items.length >= COMPOSER_COMPLETION_LIMIT) break;
            }

            if (requestId !== this.completionRequestId) return;
            this.completionItems = items.slice(0, COMPOSER_COMPLETION_LIMIT);
            this.completionActiveIndex = 0;
            this.completionMenuOpen = this.completionItems.length > 0;
            if (this.completionMenuOpen) {
                this.scrollActiveCompletionIntoView();
            }
        },

        closeCompletionMenu() {
            if (this.completionDebounceTimer) {
                clearTimeout(this.completionDebounceTimer);
                this.completionDebounceTimer = null;
            }
            this.completionRequestId += 1;
            this.completionMenuOpen = false;
            this.completionItems = [];
            this.completionActiveIndex = 0;
            this.completionQuery = '';
            this.completionRange = null;
        },

        getActiveCompletionProviders(trigger = '/') {
            const providers = [];
            const skillProvider = this.getSkillCompletionProvider(trigger);
            if (skillProvider) providers.push(skillProvider);

            for (const provider of Object.values(this.completionProviders)) {
                if (provider.trigger !== trigger) continue;
                const plugin = this.installedPlugins.find(p => p.id === provider.pluginId);
                if (!plugin || plugin.enabled === false) continue;
                providers.push(provider);
            }
            return providers;
        },

        registerCompletionProvider(config, pluginIdOverride = null) {
            const pluginId = pluginIdOverride || this._currentLoadingPlugin || config?.pluginId;
            if (!pluginId || !config?.id || typeof config.getItems !== 'function') {
                console.warn('[Plugin Input] Completion provider requires plugin id, id, and getItems');
                return false;
            }

            const fullId = `${pluginId}:${config.id}`;
            this.completionProviders[fullId] = {
                ...config,
                fullId,
                pluginId,
                trigger: config.trigger || '/'
            };
            return true;
        },

        unregisterCompletionProvider(providerId, pluginId = null) {
            const pid = pluginId || this._currentLoadingPlugin;
            if (!pid || !providerId) return false;
            const fullId = `${pid}:${providerId}`;
            const removed = Boolean(this.completionProviders[fullId]);
            delete this.completionProviders[fullId];
            if (this.completionItems.some(item => item.providerId === fullId)) {
                this.closeCompletionMenu();
            }
            return removed;
        },

        unregisterPluginCompletions(pluginId) {
            let removedActiveMenuProvider = false;
            for (const fullId of Object.keys(this.completionProviders)) {
                if (this.completionProviders[fullId].pluginId === pluginId) {
                    delete this.completionProviders[fullId];
                    removedActiveMenuProvider = removedActiveMenuProvider || this.completionItems.some(item => item.providerId === fullId);
                }
            }
            if (pluginId === SKILL_MANAGER_PLUGIN_ID) {
                this.invalidateSkillCatalog();
                removedActiveMenuProvider = true;
            }
            if (removedActiveMenuProvider) {
                this.closeCompletionMenu();
            }
        },

        async acceptCompletion(item) {
            if (!item) return;
            const context = {
                query: this.completionQuery,
                range: this.completionRange ? { ...this.completionRange } : null,
                value: this.inputMessage || '',
                selection: this.getComposerSelection()
            };
            if (typeof item.onSelect === 'function') {
                await item.onSelect(item, context);
            }
            this.closeCompletionMenu();
            this.focusComposer();
        },

        isSkillManagerEnabled() {
            return this.installedPlugins.some(plugin => plugin.id === SKILL_MANAGER_PLUGIN_ID && plugin.enabled === true);
        },

        invalidateSkillCatalog() {
            this.skillCatalogCache = null;
            this.skillCatalogLoadedAt = 0;
            if (this.completionItems.some(item => item.providerId === '__host:skill-manager-skills')) {
                this.closeCompletionMenu();
            }
            return true;
        },

        getSkillCompletionProvider(trigger) {
            if (trigger !== '/' || !this.isSkillManagerEnabled()) return null;
            return {
                fullId: '__host:skill-manager-skills',
                pluginId: SKILL_MANAGER_PLUGIN_ID,
                source: 'skills',
                icon: 'ri-sparkling-2-line',
                trigger: '/',
                getItems: async (context) => this.getSkillCompletionItems(context)
            };
        },

        async loadSkillCatalogForCompletion() {
            if (!this.isSkillManagerEnabled()) {
                return [];
            }
            const now = Date.now();
            if (this.skillCatalogCache && now - this.skillCatalogLoadedAt < SKILL_CATALOG_CACHE_MS) {
                return this.skillCatalogCache;
            }
            try {
                const res = await fetch('/api/skills');
                if (!res.ok) return [];
                const data = await res.json();
                this.skillCatalogCache = Array.isArray(data.skills) ? data.skills : [];
                this.skillCatalogLoadedAt = now;
                return this.skillCatalogCache;
            } catch (error) {
                console.error('Failed to load skill catalog:', error);
                return [];
            }
        },

        skillAliases(skill) {
            const metadata = skill?.metadata || {};
            const aliases = [];
            for (const key of ['alias', 'aliases']) {
                const value = metadata[key];
                if (Array.isArray(value)) {
                    aliases.push(...value.filter(item => typeof item === 'string'));
                } else if (typeof value === 'string') {
                    aliases.push(...value.split(',').map(item => item.trim()).filter(Boolean));
                }
            }
            if (typeof metadata.display_name === 'string') {
                aliases.push(metadata.display_name);
            }
            return aliases;
        },

        rankSkillCompletion(skill, query) {
            const normalizedQuery = (query || '').toLowerCase();
            const name = (skill.name || '').toLowerCase();
            if (!name || RESERVED_SLASH_COMMANDS.has(name) || COMMON_PATH_ROOTS.has(name)) return null;
            if (!normalizedQuery) return 100;
            if (RESERVED_SLASH_COMMANDS.has(normalizedQuery) || COMMON_PATH_ROOTS.has(normalizedQuery)) return null;
            if (name === normalizedQuery) return 0;
            if (name.startsWith(normalizedQuery)) return 10;
            if (name.includes(normalizedQuery)) return 20;

            const aliases = this.skillAliases(skill).map(alias => alias.toLowerCase());
            if (aliases.some(alias => alias === normalizedQuery)) return 30;
            if (aliases.some(alias => alias.startsWith(normalizedQuery))) return 35;
            if (aliases.some(alias => alias.includes(normalizedQuery))) return 40;

            const description = (skill.description || '').toLowerCase();
            const queryTokens = normalizedQuery.split(/[-\s]+/).filter(Boolean);
            if (queryTokens.length && queryTokens.every(token => description.includes(token))) {
                return 50;
            }
            return null;
        },

        async getSkillCompletionItems(context) {
            const skills = await this.loadSkillCatalogForCompletion();
            return skills
                .map(skill => ({ skill, rank: this.rankSkillCompletion(skill, context.query) }))
                .filter(item => item.rank !== null)
                .sort((a, b) => a.rank - b.rank || a.skill.name.localeCompare(b.skill.name))
                .slice(0, COMPOSER_COMPLETION_LIMIT)
                .map(({ skill }) => ({
                    id: `skill:${skill.name}`,
                    label: `/${skill.name}`,
                    description: skill.description || '',
                    source: 'skills',
                    icon: 'ri-sparkling-2-line',
                    type: 'skill',
                    metadata: { skill },
                    onSelect: (_item, selectContext) => this.selectSkillCompletion(skill, selectContext.range)
                }));
        },

        selectSkillCompletion(skill, range) {
            if (!skill?.name || !range) return;
            const value = this.inputMessage || '';
            let replaceStart = range.start;
            let replaceEnd = range.end;
            while (value[replaceEnd] && !/\s/.test(value[replaceEnd])) {
                replaceEnd += 1;
            }
            const suffix = value[replaceEnd] && /\s/.test(value[replaceEnd]) ? '' : ' ';
            this.replaceComposerRange(replaceStart, replaceEnd, `/${skill.name}${suffix}`);
            this.closeCompletionMenu();
        },

        isValidComposerSkillName(name) {
            return SKILL_NAME_PATTERN.test(name) && !RESERVED_SLASH_COMMANDS.has(name) && !COMMON_PATH_ROOTS.has(name);
        },

        isKnownComposerSkillName(name) {
            if (!this.isValidComposerSkillName(name) || !Array.isArray(this.skillCatalogCache)) return false;
            return this.skillCatalogCache.some(skill => skill?.name === name && skill.enabled !== false);
        },

        getComposerSkillTokenRanges(message, options = {}) {
            const text = String(message || '');
            const matches = text.matchAll(/(^|\s)\/([a-z0-9][a-z0-9-]{0,62})(?=$|\s)/g);
            const seen = new Set();
            const ranges = [];
            for (const match of matches) {
                const name = match[2];
                if (!this.isValidComposerSkillName(name)) continue;
                if (options.knownOnly && !this.isKnownComposerSkillName(name)) continue;
                const isFirstUse = !seen.has(name);
                if (isFirstUse && seen.size >= MAX_ACTIVE_SKILLS_PER_REQUEST) continue;
                if (isFirstUse) seen.add(name);
                const start = match.index + match[1].length;
                ranges.push({
                    name,
                    start,
                    end: start + name.length + 1,
                    text: text.slice(start, start + name.length + 1)
                });
            }
            return ranges;
        },

        renderComposerHighlights(message) {
            const text = String(message || '');
            if (!text) return '';

            const ranges = this.getComposerSkillTokenRanges(text, { knownOnly: true });
            if (!ranges.length) return this.escapeComposerHtml(text);

            let cursor = 0;
            let html = '';
            for (const range of ranges) {
                html += this.escapeComposerHtml(text.slice(cursor, range.start));
                html += `<span class="composer-highlight-skill">${this.escapeComposerHtml(range.text)}</span>`;
                cursor = range.end;
            }
            html += this.escapeComposerHtml(text.slice(cursor));
            return html;
        },

        async extractActiveSkillNamesFromText(message) {
            if (!this.isSkillManagerEnabled()) {
                return [];
            }
            await this.loadSkillCatalogForCompletion();
            const seen = new Set();
            const names = [];
            for (const range of this.getComposerSkillTokenRanges(message, { knownOnly: true })) {
                if (seen.has(range.name)) continue;
                seen.add(range.name);
                names.push(range.name);
            }
            return names;
        },

        async prepareOutgoingMessage() {
            const message = (this.inputMessage || '').trim();
            if (!message) {
                return {
                    message,
                    activeSkillNames: []
                };
            }
            return {
                message,
                activeSkillNames: await this.extractActiveSkillNamesFromText(message)
            };
        },

        buildSendInterceptContext(message, activeSkillNames, signal = this.abortController?.signal) {
            return {
                message,
                activeSkillNames: [...activeSkillNames],
                parsedUrl: this.parsedUrl ? {
                    url: this.parsedUrl.url,
                    title: this.parsedUrl.title
                } : null,
                attachedDocument: this.attachedDocument ? {
                    filename: this.attachedDocument.filename
                } : null,
                hasImage: Boolean(this.uploadedImageBase64),
                currentChatId: this.currentChatId,
                signal
            };
        },

        applySendInterceptResult(result, originalMessage) {
            const userMessage = result.userMessage === false ? null : (result.userMessage || originalMessage);
            if (userMessage) {
                this.messages.push({
                    role: 'user',
                    content: String(userMessage)
                });
            }

            if (result.assistantMessage) {
                this.messages.push({
                    role: 'assistant',
                    content: String(result.assistantMessage)
                });
            }

            if (result.clearInput !== false) {
                this.inputMessage = '';
                this.closeCompletionMenu();
                this.$nextTick(() => this.autoResize(this.$refs.inputBox));
            }

            if (result.clearAttachments !== false) {
                this.removeUploadedImage();
                this.removeParsedUrl();
                this.removeAttachedDocument();
            }

            if (result.refreshSkillCatalog) {
                this.invalidateSkillCatalog();
            }

            this.$nextTick(() => this.scrollToBottom());
        },

        normalizeChatEndpoint(endpoint) {
            if (ALLOWED_CHAT_ENDPOINTS.has(endpoint)) {
                return endpoint;
            }
            console.warn('[Route] Ignored non-allowlisted chat endpoint:', endpoint);
            return DEFAULT_CHAT_ENDPOINT;
        },

        buildRouteMessageBody(body) {
            const routeBody = { ...body };
            if (Array.isArray(body.active_skills)) {
                routeBody.active_skills = Object.freeze([...body.active_skills]);
            }
            return Object.freeze(routeBody);
        },

        isValidRouteMessageResult(result) {
            if (!result || typeof result !== 'object' || Array.isArray(result)) {
                return false;
            }

            const symbolKeys = Object.getOwnPropertySymbols(result);
            if (symbolKeys.length > 0) {
                console.warn('[Route] Ignored route_message result with unsupported symbol fields');
                return false;
            }

            const resultKeys = Object.getOwnPropertyNames(result);
            const extraKeys = resultKeys.filter(key => !ROUTE_MESSAGE_RESULT_KEYS.has(key));
            if (extraKeys.length > 0) {
                console.warn('[Route] Ignored route_message result with unsupported fields:', extraKeys.join(', '));
                return false;
            }

            if (!Object.prototype.hasOwnProperty.call(result, 'success') || result.success !== true) {
                console.warn('[Route] Ignored route_message result without success: true');
                return false;
            }

            if (!Object.prototype.hasOwnProperty.call(result, 'route') || typeof result.route !== 'string') {
                console.warn('[Route] Ignored route_message result without a string route');
                return false;
            }

            return true;
        },

        async resolveMessageRouteEndpoint(body) {
            const handlers = this.pluginHooks.route_message || [];
            if (!handlers.length) {
                return DEFAULT_CHAT_ENDPOINT;
            }

            const routeBody = this.buildRouteMessageBody(body);
            for (const handler of handlers) {
                if (handler._pluginId) {
                    const plugin = this.installedPlugins.find(p => p.id === handler._pluginId);
                    if (plugin && !plugin.enabled) continue;
                }

                try {
                    const result = await handler.handler(routeBody);
                    if (!result?.success) continue;
                    if (!this.isValidRouteMessageResult(result)) continue;

                    const endpoint = CHAT_ROUTE_ENDPOINTS[result.route];
                    if (endpoint) {
                        return this.normalizeChatEndpoint(endpoint);
                    }

                    console.warn('[Route] Ignored unknown chat route:', result.route);
                } catch (e) {
                    console.error('[Hook route_message] Error:', e);
                }
            }

            return DEFAULT_CHAT_ENDPOINT;
        },
        
        // Send message
        async sendMessage() {
            if (this.isGenerating) return;
            this.isGenerating = true;
            const sendController = new AbortController();
            this.abortController = sendController;
            
            try {
                const outgoing = await this.prepareOutgoingMessage();
                if (sendController.signal.aborted) return;

                let message = outgoing.message;
                const activeSkillNames = [...outgoing.activeSkillNames];
                if (!message) return;

                const interceptResult = await this.callSendInterceptors(
                    this.buildSendInterceptContext(message, activeSkillNames, sendController.signal)
                );
                if (sendController.signal.aborted) return;
                if (interceptResult?.success && interceptResult.handled) {
                    this.applySendInterceptResult(interceptResult, message);
                    return;
                }

                this.inputMessage = '';
                this.closeCompletionMenu();
                this.$nextTick(() => this.autoResize(this.$refs.inputBox));

                // Call transform_input hooks to allow plugins to modify the input
                const transformResult = await this.callHook('transform_input', message);
                if (sendController.signal.aborted) return;
                if (transformResult?.success && transformResult.content) {
                    message = transformResult.content;
                }

                this.messages.push({
                    role: 'user',
                    content: message
                });
                this.$nextTick(() => this.scrollToBottom());

                // Combine web content and document content
                let combinedContent = '';
                let contentSource = '';
                
                if (this.parsedUrl) {
                    combinedContent = this.parsedUrl.content;
                    contentSource = this.parsedUrl.url;
                }
                
                if (this.attachedDocument) {
                    if (combinedContent) {
                        combinedContent += '\n\n---\n\n';
                    }
                    combinedContent += this.attachedDocument.content;
                    contentSource = contentSource ? contentSource + ', ' + this.attachedDocument.filename : this.attachedDocument.filename;
                }
                
                let body = {
                    chat_id: this.currentChatId,
                    message: message,
                    use_rag: this.useRAG,
                    use_thinking: this.useThinking,
                    image_base64: this.uploadedImageBase64,
                    web_content: combinedContent,
                    web_url: contentSource
                };
                
                // Call before_send hooks to allow plugins to modify the request
                const beforeSendResult = await this.callHook('before_send', body);
                if (sendController.signal.aborted) return;
                if (beforeSendResult?.success && beforeSendResult.body) {
                    body = { ...body, ...beforeSendResult.body };
                }
                if (activeSkillNames.length > 0) {
                    body.active_skills = activeSkillNames;
                } else {
                    delete body.active_skills;
                }

                const endpoint = await this.resolveMessageRouteEndpoint(body);
                if (sendController.signal.aborted) return;
                
                this.removeUploadedImage();
                this.removeParsedUrl();
                this.removeAttachedDocument();
                
                if (this.settings.chat_settings.stream) {
                    await this.handleStreamResponse(body, endpoint, sendController.signal);
                } else {
                    await this.handleNormalResponse(body, endpoint, sendController.signal);
                }
                // Call after_receive hooks for post-processing
                const lastMsg = this.messages[this.messages.length - 1];
                if (lastMsg && lastMsg.role === 'assistant') {
                    const afterResult = await this.callHook('after_receive', lastMsg);
                    if (afterResult?.success && afterResult.content) {
                        lastMsg.content = afterResult.content;
                        this.messages[this.messages.length - 1] = { ...lastMsg };
                    }
                }
                
                await this.loadChats();
                
            } catch (e) {
                if (e.name === 'AbortError') {
                    // User cancelled, do nothing
                } else {
                    console.error('Failed to send message:', e);
                    this.showToast(this.t('sendFailed') + ': ' + e.message, 'error');
                }
            } finally {
                if (this.abortController === sendController) {
                    this.abortController = null;
                    this.isGenerating = false;
                } else if (this.abortController === null) {
                    this.isGenerating = false;
                }
            }
        },

        createHermesRunState(chatId = '') {
            return {
                runId: '',
                status: '',
                events: [],
                pendingApproval: null,
                approvalSubmitting: false,
                approvalError: '',
                approvalBridgeResolvedKey: '',
                chatId: chatId || this.currentChatId || ''
            };
        },

        ensureHermesRunState(message) {
            if (!message.hermesRun) {
                message.hermesRun = this.createHermesRunState();
            }
            if (!message.hermesRun.events) {
                message.hermesRun.events = [];
            }
            if (!message.hermesRun.chatId && this.currentChatId) {
                message.hermesRun.chatId = this.currentChatId;
            }
            return message.hermesRun;
        },

        normalizeHermesRunEvent(event) {
            if (!event || typeof event !== 'object' || Array.isArray(event)) {
                return null;
            }

            const type = typeof event.type === 'string' ? event.type : '';
            if (!type) return null;

            const normalized = { type };
            const stringFields = [
                'run_id',
                'status',
                'tool',
                'preview',
                'error',
                'command',
                'description',
                'choice'
            ];
            for (const field of stringFields) {
                if (event[field] !== undefined && event[field] !== null) {
                    normalized[field] = String(event[field]);
                }
            }

            if (Array.isArray(event.pattern_keys)) {
                normalized.pattern_keys = event.pattern_keys
                    .map(item => String(item))
                    .filter(Boolean)
                    .slice(0, 20);
            }
            if (Array.isArray(event.choices)) {
                normalized.choices = event.choices
                    .map(item => String(item))
                    .filter(Boolean);
            }
            if (Number.isFinite(event.duration_ms)) {
                normalized.duration_ms = Math.round(event.duration_ms);
            }
            if (typeof event.resolved === 'boolean' || Number.isFinite(event.resolved)) {
                normalized.resolved = event.resolved;
            }
            if (event.usage && typeof event.usage === 'object' && !Array.isArray(event.usage)) {
                normalized.usage = {};
                for (const [key, value] of Object.entries(event.usage)) {
                    if (Number.isFinite(value)) {
                        normalized.usage[key] = value;
                    }
                }
            }
            return normalized;
        },

        hermesApprovalRequestKey(event) {
            if (!event) return '';
            const patterns = Array.isArray(event.pattern_keys) ? event.pattern_keys.join('|') : '';
            return [
                event.run_id || '',
                event.command || '',
                event.description || '',
                patterns
            ].join('\n');
        },

        isHermesRunTerminalStatus(status) {
            return ['completed', 'succeeded', 'failed', 'cancelled', 'canceled', 'stopped'].includes(status || '');
        },

        markActiveHermesRunCancelled() {
            for (let i = this.messages.length - 1; i >= 0; i -= 1) {
                const msg = this.messages[i];
                const run = msg?.hermesRun;
                if (!run || !Array.isArray(run.events) || !run.events.length) continue;
                if (this.isHermesRunTerminalStatus(run.status)) return;
                this.applyHermesRunEvent(msg, {
                    type: 'run.cancelled',
                    run_id: run.runId || '',
                    status: 'cancelled'
                }, i);
                return;
            }
        },

        applyHermesRunEvent(message, event, msgIndex = -1) {
            const normalized = this.normalizeHermesRunEvent(event);
            if (!normalized) return;

            const hermesRun = this.ensureHermesRunState(message);
            if (
                normalized.type === 'approval.request' &&
                (
                    (
                        hermesRun.pendingApproval &&
                        this.hermesApprovalRequestKey(hermesRun.pendingApproval) === this.hermesApprovalRequestKey(normalized)
                    ) ||
                    hermesRun.approvalBridgeResolvedKey === this.hermesApprovalRequestKey(normalized)
                )
            ) {
                return;
            }

            normalized._id = `${normalized.type}-${hermesRun.events.length}`;
            if (normalized.run_id) {
                hermesRun.runId = normalized.run_id;
            }
            if (normalized.status) {
                hermesRun.status = normalized.status;
            }

            if (normalized.type === 'approval.request') {
                hermesRun.status = 'pending_approval';
                hermesRun.pendingApproval = normalized;
                hermesRun.approvalSubmitting = false;
                hermesRun.approvalError = '';
            } else if (normalized.type === 'approval.responded') {
                hermesRun.pendingApproval = null;
                hermesRun.approvalSubmitting = false;
                hermesRun.approvalError = '';
                hermesRun.approvalBridgeResolvedKey = '';
                hermesRun.status = normalized.status || 'running';
            } else if (normalized.type === 'run.completed') {
                hermesRun.pendingApproval = null;
                hermesRun.approvalSubmitting = false;
                hermesRun.approvalError = '';
                hermesRun.approvalBridgeResolvedKey = '';
                hermesRun.status = 'completed';
            } else if (normalized.type === 'run.failed') {
                hermesRun.pendingApproval = null;
                hermesRun.approvalSubmitting = false;
                hermesRun.approvalBridgeResolvedKey = '';
                hermesRun.status = 'failed';
            } else if (normalized.type === 'run.cancelled') {
                hermesRun.pendingApproval = null;
                hermesRun.approvalSubmitting = false;
                hermesRun.approvalBridgeResolvedKey = '';
                hermesRun.status = 'cancelled';
            } else if (normalized.type === 'run.started' && !hermesRun.status) {
                hermesRun.status = normalized.status || 'running';
            }

            hermesRun.events.push(normalized);
            this.commitHermesRunMessage(message, msgIndex);
        },

        commitHermesRunMessage(message, msgIndex = -1) {
            if (!message.hermesRun) return;
            message.hermesRun = {
                ...message.hermesRun,
                events: [...message.hermesRun.events],
                pendingApproval: message.hermesRun.pendingApproval ? { ...message.hermesRun.pendingApproval } : null
            };
            if (msgIndex >= 0) {
                this.messages[msgIndex] = { ...message };
            }
            this.$nextTick(() => this.scrollToBottom());
        },

        hermesRunStatusLabel(status) {
            const normalized = String(status || '').toLowerCase();
            const labels = {
                started: this.t('hermesRunStatusStarted'),
                queued: this.t('hermesRunStatusStarted'),
                running: this.t('hermesRunStatusRunning'),
                in_progress: this.t('hermesRunStatusRunning'),
                pending_approval: this.t('hermesRunStatusPendingApproval'),
                completed: this.t('hermesRunStatusCompleted'),
                succeeded: this.t('hermesRunStatusCompleted'),
                failed: this.t('hermesRunStatusFailed'),
                cancelled: this.t('hermesRunStatusCancelled'),
                canceled: this.t('hermesRunStatusCancelled')
            };
            return labels[normalized] || status || this.t('hermesRunStatusRunning');
        },

        hermesRunEventTitle(event) {
            const titles = {
                'run.started': this.t('hermesRunEventRunStarted'),
                'tool.started': this.t('hermesRunEventToolStarted'),
                'tool.completed': this.t('hermesRunEventToolCompleted'),
                'reasoning.available': this.t('hermesRunEventReasoning'),
                'approval.request': this.t('hermesRunEventApprovalRequest'),
                'approval.responded': this.t('hermesRunEventApprovalResponded'),
                'run.completed': this.t('hermesRunEventRunCompleted'),
                'run.failed': this.t('hermesRunEventRunFailed'),
                'run.cancelled': this.t('hermesRunEventRunCancelled')
            };
            return titles[event?.type] || event?.type || this.t('hermesRun');
        },

        hermesRunEventIcon(event) {
            const icons = {
                'run.started': 'ri-play-circle-line',
                'tool.started': 'ri-tools-line',
                'tool.completed': 'ri-checkbox-circle-line',
                'reasoning.available': 'ri-lightbulb-line',
                'approval.request': 'ri-shield-keyhole-line',
                'approval.responded': 'ri-check-double-line',
                'run.completed': 'ri-checkbox-circle-line',
                'run.failed': 'ri-error-warning-line',
                'run.cancelled': 'ri-stop-circle-line'
            };
            return icons[event?.type] || 'ri-terminal-box-line';
        },

        hermesRunEventClass(event) {
            const typeClass = String(event?.type || 'event').replace(/[^a-z0-9_-]+/gi, '-').toLowerCase();
            const statusClass = String(event?.status || '').replace(/[^a-z0-9_-]+/gi, '-').toLowerCase();
            return {
                [`hermes-event-${typeClass}`]: true,
                [`status-${statusClass}`]: Boolean(statusClass)
            };
        },

        formatHermesDuration(ms) {
            if (!Number.isFinite(ms)) return '';
            if (ms < 1000) return `${ms} ms`;
            return `${(ms / 1000).toFixed(ms < 10000 ? 1 : 0)} s`;
        },

        hasHermesDuration(event) {
            return Number.isFinite(event?.duration_ms);
        },

        isHermesPendingApprovalEvent(message, event) {
            const pending = message?.hermesRun?.pendingApproval;
            return Boolean(pending && event && pending._id === event._id);
        },

        async submitHermesApproval(message, choice, msgIndex = -1) {
            const targetIndex = msgIndex >= 0 ? msgIndex : this.messages.indexOf(message);
            if (
                targetIndex >= 0 &&
                this.messages[targetIndex] !== message &&
                this.messages[targetIndex]?.hermesRun?.runId !== message?.hermesRun?.runId
            ) {
                return;
            }
            const targetMessage = targetIndex >= 0 ? this.messages[targetIndex] : message;
            const hermesRun = targetMessage?.hermesRun;
            const runId = hermesRun?.runId;
            const chatId = hermesRun?.chatId;
            if (!hermesRun || !runId || !chatId || hermesRun.approvalSubmitting) {
                return;
            }

            hermesRun.approvalSubmitting = true;
            hermesRun.approvalError = '';
            this.commitHermesRunMessage(targetMessage, targetIndex);

            try {
                const response = await fetch(`/api/hermes/runs/${encodeURIComponent(runId)}/approval`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        chat_id: chatId,
                        choice,
                        resolve_all: false
                    })
                });
                let data = {};
                try {
                    data = await response.json();
                } catch (_) {
                    data = {};
                }
                if (!response.ok || data.success === false) {
                    throw new Error(data.error || this.t('hermesApprovalError'));
                }
                hermesRun.status = data.status || hermesRun.status || 'running';
                hermesRun.approvalBridgeResolvedKey = this.hermesApprovalRequestKey(hermesRun.pendingApproval);
                hermesRun.pendingApproval = null;
                hermesRun.approvalSubmitting = false;
                hermesRun.approvalError = '';
                this.commitHermesRunMessage(targetMessage, targetIndex);
            } catch (error) {
                hermesRun.approvalSubmitting = false;
                hermesRun.approvalError = error.message || this.t('hermesApprovalError');
                this.commitHermesRunMessage(targetMessage, targetIndex);
            }
        },
        
        // Handle stream response (NDJSON format) - TRUE STREAMING
        async handleStreamResponse(body, endpoint = DEFAULT_CHAT_ENDPOINT, signal = this.abortController?.signal) {
            const chatEndpoint = this.normalizeChatEndpoint(endpoint);
            const res = await fetch(chatEndpoint, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(body),
                signal
            });
            
            if (!res.ok) {
                const errText = await res.text();
                throw new Error(errText || 'Request failed');
            }
            
            const assistantMsg = {
                role: 'assistant',
                content: '',
                thinking: '',
                references: [],
                showThinking: false,
                hermesRun: this.createHermesRunState()
            };
            this.messages.push(assistantMsg);
            const msgIndex = this.messages.length - 1;
            
            const reader = res.body.getReader();
            const decoder = new TextDecoder();
            let buffer = '';
            
            try {
                while (true) {
                    const { done, value } = await reader.read();
                    if (done) break;
                    
                    buffer += decoder.decode(value, { stream: true });
                    
                    // Process complete lines
                    let newlineIdx;
                    while ((newlineIdx = buffer.indexOf('\n')) !== -1) {
                        const line = buffer.slice(0, newlineIdx).trim();
                        buffer = buffer.slice(newlineIdx + 1);
                        
                        if (!line) continue;
                        
                        try {
                            const parsed = JSON.parse(line);
                            
                            if (parsed.chat_id) {
                                this.currentChatId = parsed.chat_id;
                                if (assistantMsg.hermesRun) {
                                    assistantMsg.hermesRun.chatId = parsed.chat_id;
                                }
                            }

                            if (parsed.hermes_run) {
                                this.applyHermesRunEvent(assistantMsg, parsed.hermes_run, msgIndex);
                            }
                            
                            // Handle thinking/reasoning content
                            if (parsed.thinking) {
                                // Preserve showThinking state when updating
                                const currentShowThinking = this.messages[msgIndex]?.showThinking || false;
                                assistantMsg.thinking += parsed.thinking;
                                assistantMsg.showThinking = currentShowThinking;
                                this.messages[msgIndex] = { ...assistantMsg };
                                this.$nextTick(() => this.scrollToBottom());
                            }
                            
                            if (parsed.content) {
                                // Preserve showThinking state when updating
                                const currentShowThinking = this.messages[msgIndex]?.showThinking || false;
                                assistantMsg.content += parsed.content;
                                assistantMsg.showThinking = currentShowThinking;
                                this.messages[msgIndex] = { ...assistantMsg };
                                this.$nextTick(() => this.scrollToBottom());
                            }
                            
                            if (parsed.references) {
                                const currentShowThinking = this.messages[msgIndex]?.showThinking || false;
                                assistantMsg.references = parsed.references;
                                assistantMsg.showThinking = currentShowThinking;
                                this.messages[msgIndex] = { ...assistantMsg };
                                this.$nextTick(() => this.scrollToBottom());
                            }
                            
                            if (parsed.error) {
                                assistantMsg.content = 'Error: ' + parsed.error;
                                this.messages[msgIndex] = { ...assistantMsg };
                            }
                        } catch (e) {
                            // ignore parse errors
                        }
                    }
                }
            } catch (e) {
                if (e.name === 'AbortError') {
                    // User stopped generation, keep partial content
                    try { await reader.cancel(); } catch (_) { /* ignore */ }
                } else {
                    throw e;
                }
            }
        },
        
        // Handle normal response
        async handleNormalResponse(body, endpoint = DEFAULT_CHAT_ENDPOINT, signal = this.abortController?.signal) {
            const chatEndpoint = this.normalizeChatEndpoint(endpoint);
            const res = await fetch(chatEndpoint, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(body),
                signal
            });
            
            const data = await res.json();
            
            if (!res.ok) {
                throw new Error(data.error || 'Request failed');
            }
            
            if (!this.currentChatId && data.chat_id) {
                this.currentChatId = data.chat_id;
            }
            
            this.messages.push({
                role: 'assistant',
                content: data.content,
                thinking: data.thinking || '',
                references: data.references || []
            });
            this.$nextTick(() => this.scrollToBottom());
        },
        
        // Handle file upload (documents) with progress
        async handleFileUpload(event) {
            const file = event.target.files[0];
            if (!file) return;
            
            const formData = new FormData();
            formData.append('file', file);
            
            // Show progress
            this.uploadProgress = { show: true, filename: file.name, progress: 0, status: 'uploading' };
            
            try {
                const res = await fetch('/api/documents', {
                    method: 'POST',
                    body: formData
                });
                
                if (!res.ok) {
                    const error = await res.text();
                    throw new Error(error);
                }
                
                // Read progress stream
                const reader = res.body.getReader();
                const decoder = new TextDecoder();
                let buffer = '';
                
                while (true) {
                    const { done, value } = await reader.read();
                    if (done) break;
                    
                    buffer += decoder.decode(value, { stream: true });
                    
                    let newlineIdx;
                    while ((newlineIdx = buffer.indexOf('\n')) !== -1) {
                        const line = buffer.slice(0, newlineIdx).trim();
                        buffer = buffer.slice(newlineIdx + 1);
                        
                        if (!line) continue;
                        
                        try {
                            const data = JSON.parse(line);
                            
                            if (data.status === 'chunking') {
                                this.uploadProgress.status = 'chunking';
                                this.uploadProgress.total = data.total;
                            } else if (data.status === 'embedding') {
                                this.uploadProgress.status = 'embedding';
                                this.uploadProgress.progress = data.progress;
                                this.uploadProgress.current = data.current;
                                this.uploadProgress.total = data.total;
                            } else if (data.status === 'done') {
                                this.uploadProgress.show = false;
                                this.showToast(`"${file.name}" ${this.t('uploadSuccess')}`, 'success');
                                await this.loadDocuments();
                            }
                        } catch (e) {
                            // ignore parse errors
                        }
                    }
                }
            } catch (e) {
                this.uploadProgress.show = false;
                this.showToast(this.t('uploadFailed') + ': ' + e.message, 'error');
            }
            
            event.target.value = '';
        },
        
        // Check if browser supports WebP encoding
        supportsWebP() {
            const canvas = document.createElement('canvas');
            canvas.width = 1;
            canvas.height = 1;
            return canvas.toDataURL('image/webp').startsWith('data:image/webp');
        },
        
        // Compress image using Canvas API, target 500KB, max 1120px long edge
        async compressImage(file, targetSizeMB = 0.5) {
            const targetSize = targetSizeMB * 1024 * 1024; // 500KB default
            const maxLongEdge = 1120; // Maximum long edge dimension
            
            return new Promise((resolve, reject) => {
                const img = new Image();
                const url = URL.createObjectURL(file);
                
                img.onload = async () => {
                    URL.revokeObjectURL(url);
                    
                    // Detect format support
                    const useWebP = this.supportsWebP();
                    const mimeType = useWebP ? 'image/webp' : 'image/jpeg';
                    const ext = useWebP ? '.webp' : '.jpg';
                    
                    let { width, height } = img;
                    const originalWidth = width;
                    const originalHeight = height;
                    
                    // Resize to max 1120px on long edge while maintaining aspect ratio
                    const longEdge = Math.max(width, height);
                    if (longEdge > maxLongEdge) {
                        const ratio = maxLongEdge / longEdge;
                        width = Math.round(width * ratio);
                        height = Math.round(height * ratio);
                    }
                    
                    const canvas = document.createElement('canvas');
                    const ctx = canvas.getContext('2d');
                    
                    // Helper to create blob
                    const createBlob = (w, h, quality) => {
                        return new Promise((res) => {
                            canvas.width = w;
                            canvas.height = h;
                            ctx.fillStyle = '#FFFFFF';
                            ctx.fillRect(0, 0, w, h);
                            ctx.drawImage(img, 0, 0, w, h);
                            canvas.toBlob((blob) => res(blob), mimeType, quality);
                        });
                    };
                    
                    // Try compression with different quality levels until under target size
                    const qualityLevels = [0.92, 0.85, 0.75, 0.65, 0.55, 0.45, 0.35, 0.25];
                    
                    let bestBlob = null;
                    
                    // Try different quality levels with the resized dimensions
                    for (const quality of qualityLevels) {
                        const blob = await createBlob(width, height, quality);
                        if (blob && blob.size <= targetSize) {
                            bestBlob = blob;
                            break;
                        }
                        // Keep the smallest one we've seen
                        if (!bestBlob || (blob && blob.size < bestBlob.size)) {
                            bestBlob = blob;
                        }
                    }
                    
                    // If still too large, try scaling down further
                    if (bestBlob && bestBlob.size > targetSize) {
                        const scaleLevels = [0.9, 0.8, 0.7, 0.6, 0.5];
                        for (const scale of scaleLevels) {
                            const w = Math.round(width * scale);
                            const h = Math.round(height * scale);
                            
                            for (const quality of qualityLevels) {
                                const blob = await createBlob(w, h, quality);
                                if (blob && blob.size <= targetSize) {
                                    bestBlob = blob;
                                    break;
                                }
                                if (blob && blob.size < bestBlob.size) {
                                    bestBlob = blob;
                                }
                            }
                            
                            if (bestBlob && bestBlob.size <= targetSize) {
                                break;
                            }
                        }
                    }
                    
                    if (!bestBlob) {
                        reject(new Error('Compression failed'));
                        return;
                    }
                    
                    const newName = file.name.replace(/\.[^.]+$/, ext);
                    resolve(new File([bestBlob], newName, { type: mimeType }));
                };
                
                img.onerror = () => {
                    URL.revokeObjectURL(url);
                    reject(new Error('Failed to load image'));
                };
                
                img.src = url;
            });
        },
        
        // Handle image upload
        async handleImageUpload(event) {
            const file = event.target.files[0];
            if (!file) return;
            if (!this.chatModelSupportsVision()) {
                event.target.value = '';
                return;
            }
            
            try {
                // Compress image before upload
                const compressedFile = await this.compressImage(file);
                
                const formData = new FormData();
                formData.append('file', compressedFile);
                
                const res = await fetch('/api/upload/image', {
                    method: 'POST',
                    body: formData
                });
                
                if (res.ok) {
                    const data = await res.json();
                    this.uploadedImage = file.name; // Keep original name for display
                    this.uploadedImageBase64 = data.base64;
                } else {
                    const error = await res.json();
                    throw new Error(error.error);
                }
            } catch (e) {
                this.showToast(this.t('uploadFailed') + ': ' + e.message, 'error');
            }
            
            event.target.value = '';
        },
        
        // Handle logo upload
        handleLogoUpload(event) {
            const file = event.target.files[0];
            if (!file) return;
            
            const reader = new FileReader();
            reader.onload = (e) => {
                this.settings.ui_settings.logo_data = e.target.result;
                this.updateFavicon(e.target.result);
            };
            reader.readAsDataURL(file);
            
            event.target.value = '';
        },
        
        // Update favicon
        updateFavicon(dataUrl) {
            const favicon = document.getElementById('favicon');
            if (dataUrl) {
                favicon.href = dataUrl;
            } else {
                // Empty favicon when no logo is set
                favicon.href = 'data:,';
            }
            document.title = this.settings.ui_settings.logo_text || 'ChatRaw';
        },
        
        // Handle avatar upload
        handleAvatarUpload(event, type) {
            const file = event.target.files[0];
            if (!file) return;
            
            const reader = new FileReader();
            reader.onload = (e) => {
                if (type === 'user') {
                    this.settings.ui_settings.user_avatar = e.target.result;
                } else {
                    this.settings.ui_settings.assistant_avatar = e.target.result;
                }
            };
            reader.readAsDataURL(file);
            
            event.target.value = '';
        },
        
        // Remove uploaded image
        removeUploadedImage() {
            this.uploadedImage = null;
            this.uploadedImageBase64 = '';
        },
        
        // Handle document upload for chat attachment
        async handleDocumentUpload(event) {
            const file = event.target.files[0];
            if (!file) return;
            
            this.isUploadingDocument = true;
            
            try {
                // Check if any plugin can handle this file type
                const ext = '.' + (file.name.split('.').pop() || '').toLowerCase();
                const parseDocHandlers = this.pluginHooks.parse_document || [];
                
                let pluginHandled = false;
                
                // Try to find a plugin that can parse this file type
                for (const handler of parseDocHandlers) {
                    // Skip if plugin is disabled
                    if (handler._pluginId) {
                        const plugin = this.installedPlugins.find(p => p.id === handler._pluginId);
                        if (!plugin || !plugin.enabled) continue;
                    }
                    
                    // Check if this handler supports the file type
                    const supportedTypes = handler.fileTypes || [];
                    if (supportedTypes.includes(ext) || supportedTypes.includes(ext.toLowerCase())) {
                        try {
                            // Get plugin settings if available
                            const settings = handler._pluginId ? this.getPluginSettings(handler._pluginId) : {};
                            
                            // Call the plugin handler to parse the file
                            const result = await handler.handler(file, settings);
                            
                            if (result?.success && result.content) {
                                // Plugin successfully parsed the file
                                this.attachedDocument = {
                                    filename: file.name,
                                    content: result.content
                                };
                                this.showToast(this.t('documentAttached') + ': ' + file.name, 'success');
                                pluginHandled = true;
                                break;
                            } else if (result?.error) {
                                // Plugin returned an error
                                this.showToast(this.t('uploadFailed') + ': ' + result.error, 'error');
                                pluginHandled = true;
                                break;
                            }
                            // If result is null/undefined or not success, continue to try other handlers or fallback
                        } catch (pluginError) {
                            console.error(`[Plugin ${handler._pluginId}] Parse error:`, pluginError);
                            // Continue to try other handlers or fallback to backend
                        }
                    }
                }
                
                // If no plugin handled the file, fall back to backend
                if (!pluginHandled) {
                    const formData = new FormData();
                    formData.append('file', file);
                    
                    const res = await fetch('/api/upload/document', {
                        method: 'POST',
                        body: formData
                    });
                    
                    if (!res.ok) {
                        const text = await res.text();
                        try {
                            const data = JSON.parse(text);
                            throw new Error(data.error || `HTTP ${res.status}`);
                        } catch {
                            throw new Error(`HTTP ${res.status}: ${text.substring(0, 100)}`);
                        }
                    }
                    
                    const data = await res.json();
                    
                    if (data.success) {
                        this.attachedDocument = {
                            filename: data.filename,
                            content: data.content
                        };
                        this.showToast(this.t('documentAttached') + ': ' + data.filename, 'success');
                    } else {
                        this.showToast(this.t('uploadFailed') + ': ' + (data.error || 'Unknown error'), 'error');
                    }
                }
            } catch (e) {
                console.error('Document upload error:', e);
                this.showToast(this.t('uploadFailed') + ': ' + (e.message || 'Unknown error'), 'error');
            } finally {
                this.isUploadingDocument = false;
            }
            
            event.target.value = '';
        },
        
        // Remove attached document
        removeAttachedDocument() {
            this.attachedDocument = null;
        },
        
        // Get document accept types (base types + plugin types)
        getDocumentAcceptTypes() {
            // Base supported file types
            const baseTypes = ['.pdf', '.docx', '.doc', '.txt', '.md'];
            
            // Collect fileTypes from enabled plugins
            const pluginTypes = this.installedPlugins
                .filter(p => p.enabled && p.fileTypes)
                .flatMap(p => p.fileTypes);
            
            // Merge and deduplicate
            const allTypes = [...new Set([...baseTypes, ...pluginTypes])];
            return allTypes.join(',');
        },
        
        // Toggle URL input popup
        toggleUrlInput() {
            this.showUrlInput = !this.showUrlInput;
            if (this.showUrlInput) {
                this.urlInputValue = '';
                this.$nextTick(() => {
                    const input = document.querySelector('.url-input-popup input');
                    if (input) input.focus();
                });
            }
        },
        
        // Parse URL (try url_parser plugin first, then fallback to built-in)
        async parseUrl() {
            const url = this.urlInputValue.trim();
            if (!url) return;

            this.isParsingUrl = true;

            try {
                let data = null;
                const parseUrlHandlers = this.pluginHooks.parse_url || [];
                let urlParserPluginId = null;
                for (const h of parseUrlHandlers) {
                    if (h._pluginId) {
                        const p = this.installedPlugins.find(x => x.id === h._pluginId);
                        if (p && p.enabled) {
                            urlParserPluginId = p.id;
                            break;
                        }
                    }
                }

                if (urlParserPluginId) {
                    const settings = this.getPluginSettings(urlParserPluginId);
                    const parserMode = settings.parser_mode || 'browser';

                    if (parserMode === 'browser') {
                        const rawRes = await fetch('/api/fetch-raw-url', {
                            method: 'POST',
                            headers: { 'Content-Type': 'application/json' },
                            body: JSON.stringify({ url })
                        });
                        const rawData = await rawRes.json();
                        if (rawData.success && rawData.html != null) {
                            const result = await this.callHook('parse_url', url, rawData.html, settings);
                            if (result?.success && result.title != null && result.content != null) {
                                data = { success: true, title: result.title, content: result.content, url: url };
                            }
                        }
                    } else {
                        const result = await this.callHook('parse_url', url, null, settings);
                        if (result?.success && result.title != null && result.content != null) {
                            data = { success: true, title: result.title, content: result.content, url: url };
                        }
                    }
                }

                if (!data) {
                    const res = await fetch('/api/parse-url', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ url })
                    });
                    data = await res.json();
                }

                if (data.success) {
                    this.parsedUrl = {
                        title: data.title,
                        content: data.content,
                        url: data.url
                    };
                    this.parsedUrlTitle = data.title;
                    this.showUrlInput = false;
                    this.urlInputValue = '';
                    this.showToast(this.t('urlAttached') + ': ' + data.title, 'success');
                } else {
                    this.showToast(this.t('parseFailed') + ': ' + (data.error || 'Unknown error'), 'error');
                }
            } catch (e) {
                this.showToast(this.t('parseFailed') + ': ' + e.message, 'error');
            } finally {
                this.isParsingUrl = false;
            }
        },
        
        // Remove parsed URL
        removeParsedUrl() {
            this.parsedUrl = null;
            this.parsedUrlTitle = '';
        },
        
        // Cancel URL input
        cancelUrlInput() {
            this.showUrlInput = false;
            this.urlInputValue = '';
        },
        
        // Delete document
        async deleteDocument(id) {
            if (!confirm('Delete this shared document? Other users will lose access to it.')) return;
            try {
                const response = await fetch(`/api/documents/${id}`, { method: 'DELETE' });
                if (!response.ok) {
                    const result = await response.json();
                    throw new Error(result.detail || this.t('deleteFailed'));
                }
                this.documents = this.documents.filter(d => d.id !== id);
                this.showToast(this.t('documentDeleted'), 'success');
            } catch (e) {
                this.showToast(this.t('deleteFailed'), 'error');
            }
        },
        
        // Save and verify model
        async saveAndVerifyModel(model, index) {
            model.status = 'loading';
            model.verifyMessage = '';
            
            try {
                // Set name to model_id if empty
                if (!model.name) {
                    model.name = model.model_id || 'Unnamed';
                }
                
                // Save model config
                const saveRes = await fetch('/api/models', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        ...model,
                        api_key_action: model.api_key_action === 'clear'
                            ? 'clear'
                            : (model.api_key ? 'replace' : 'preserve')
                    })
                });
                
                if (!saveRes.ok) {
                    throw new Error('Failed to save');
                }
                
                const savedModel = await saveRes.json();
                if (savedModel.id) {
                    model.id = savedModel.id;
                }
                model.api_key_configured = savedModel.api_key_configured;
                model.api_key = '';
                model.api_key_action = 'preserve';
                
                // Verify model connection
                const verifyRes = await fetch('/api/models/verify', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        id: model.id,
                        api_url: model.api_url,
                        api_key: model.api_key,
                        model_id: model.model_id,
                        type: model.type
                    })
                });
                
                const verifyData = await verifyRes.json();
                
                if (verifyRes.ok && verifyData.success) {
                    model.status = 'success';
                    model.verifyMessage = this.t('verifySuccess');
                } else {
                    model.status = 'error';
                    model.verifyMessage = verifyData.error || this.t('verifyFailed');
                }
                
            } catch (e) {
                model.status = 'error';
                model.verifyMessage = e.message || this.t('verifyFailed');
            }
        },
        
        // Save all settings
        async saveAllSettings() {
            try {
                // Save settings
                await fetch('/api/settings', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(this.settings)
                });
                
                // Save model configs
                for (const model of this.models) {
                    // Set name to model_id if empty
                    if (!model.name) {
                        model.name = model.model_id || 'Unnamed';
                    }
                    await fetch('/api/models', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({
                            ...model,
                            api_key_action: model.api_key_action === 'clear'
                                ? 'clear'
                                : (model.api_key ? 'replace' : 'preserve')
                        })
                    });
                }
                
                this.applyTheme();
                this.showSettings = false;
                this.showToast(this.t('settingsSaved'), 'success');
                
                await this.loadModels();
                
            } catch (e) {
                this.showToast(this.t('saveFailed') + ': ' + e.message, 'error');
            }
        },
        
        // Copy assistant message content (raw markdown text only)
        async copyMessage(content, event) {
            if (!content) return;
            try {
                await navigator.clipboard.writeText(content);
                // Visual feedback: icon swap
                const btn = event.currentTarget;
                const icon = btn.querySelector('i');
                const originalClass = icon.className;
                icon.className = 'ri-check-line';
                btn.classList.add('copied');
                setTimeout(() => {
                    icon.className = originalClass;
                    btn.classList.remove('copied');
                }, 2000);
            } catch (err) {
                // Fallback for older browsers / HTTP context
                const textarea = document.createElement('textarea');
                textarea.value = content;
                textarea.style.position = 'fixed';
                textarea.style.opacity = '0';
                document.body.appendChild(textarea);
                textarea.select();
                document.execCommand('copy');
                document.body.removeChild(textarea);
                this.showToast(this.t('copied') || 'Copied!');
            }
        },
        
        // Render Markdown
        renderMarkdown(content) {
            return window.ChatRawContentSecurity.renderMarkdown(content);
        },
        
        // Scroll to bottom
        scrollToBottom() {
            const container = this.$refs.messagesContainer;
            if (container) {
                container.scrollTop = container.scrollHeight;
            }
        },
        
        // Auto resize textarea
        autoResize(el) {
            el.style.height = 'auto';
            el.style.height = Math.min(el.scrollHeight, 200) + 'px';
            if (el === this.$refs.inputBox) {
                this.syncComposerHighlightScroll();
            }
        },
        
        // Show toast
        showToast(message, type = '') {
            this.toast.message = message;
            this.toast.type = type;
            this.toast.show = true;
            
            setTimeout(() => {
                this.toast.show = false;
            }, 3000);
        },
        
        // ============ Plugin Toolbar Extension ============
        
        // Get sorted plugin buttons (only from enabled plugins)
        getSortedPluginButtons() {
            return [...this.pluginToolbarButtons]
                .filter(btn => {
                    // Only show buttons from enabled plugins
                    const plugin = this.installedPlugins?.find(p => p.id === btn.pluginId);
                    return plugin?.enabled !== false;
                })
                .sort((a, b) => (a.order || 100) - (b.order || 100));
        },
        
        // Computed: Visible plugin buttons (max 5)
        get visiblePluginButtons() {
            return this.getSortedPluginButtons().slice(0, 5);
        },
        
        // Computed: Hidden plugin buttons (overflow into "More" menu)
        get hiddenPluginButtons() {
            return this.getSortedPluginButtons().slice(5);
        },
        
        // Get localized button label
        getPluginButtonLabel(btn) {
            const lang = this.lang || 'en';
            return btn.label?.[lang] || btn.label?.en || btn.id;
        },
        
        // Handle plugin button click
        async handlePluginButtonClick(btn) {
            if (btn.loading) return;
            try {
                await btn.onClick?.(btn);
            } catch (error) {
                console.error(`[Plugin ${btn.pluginId}] Button click error:`, error);
                // Reset loading state on error
                btn.loading = false;
            }
        },
        
        // Close plugin fullscreen modal
        closePluginFullscreenModal() {
            if (this.pluginFullscreenModal.onClose) {
                try {
                    this.pluginFullscreenModal.onClose();
                } catch (e) {
                    console.error('[Plugin] Modal onClose error:', e);
                }
            }
            this.pluginFullscreenModal.show = false;
            this.pluginFullscreenModal.content = '';
            this.pluginFullscreenModal.onClose = null;
            this.pluginFullscreenModal.pluginId = null;
        },
        
        // ============ Plugin System ============
        
        // Track which plugin registered which hooks
        pluginHookRegistry: {},  // { pluginId: [{ hookName, handler }] }
        
        // Initialize plugin system
        initPluginSystem() {
            // Track current loading plugin
            this._currentLoadingPlugin = null;
            
            // Reference to app instance for closures
            const appInstance = this;

            class ModuleSdkError extends Error {
                constructor(message, code, status) {
                    super(message);
                    this.name = 'ModuleSdkError';
                    this.code = code || 'module_request_failed';
                    this.status = status || 0;
                }
            }

            const moduleRequest = async (path, options = {}) => {
                const response = await fetch(path, {
                    credentials: 'same-origin',
                    ...options
                });
                let payload = null;
                try {
                    payload = await response.json();
                } catch (_error) {
                    payload = null;
                }
                if (!response.ok) {
                    throw new ModuleSdkError(
                        payload?.detail || 'Module request failed',
                        payload?.code || 'module_request_failed',
                        response.status
                    );
                }
                return payload;
            };

            const taskPath = taskId => (
                `/api/module-tasks/${encodeURIComponent(taskId)}`
            );

            const parseSseBlock = block => {
                let id = null;
                let event = 'message';
                const data = [];
                for (const line of block.split(/\r?\n/)) {
                    if (!line || line.startsWith(':')) continue;
                    const separator = line.indexOf(':');
                    const field = separator < 0 ? line : line.slice(0, separator);
                    let value = separator < 0 ? '' : line.slice(separator + 1);
                    if (value.startsWith(' ')) value = value.slice(1);
                    if (field === 'id') id = value;
                    else if (field === 'event') event = value;
                    else if (field === 'data') data.push(value);
                }
                if (!data.length) return null;
                const numericId = Number(id);
                if (!Number.isInteger(numericId) || numericId < 1) {
                    throw new ModuleSdkError(
                        'Module event stream returned an invalid cursor',
                        'invalid_event_cursor',
                        502
                    );
                }
                return {
                    id: numericId,
                    event,
                    data: JSON.parse(data.join('\n'))
                };
            };

            const subscribe = (taskId, listener = null) => {
                if (typeof taskId !== 'string' || !taskId) {
                    throw new ModuleSdkError(
                        'taskId is required',
                        'invalid_sdk_argument',
                        0
                    );
                }
                appInstance.moduleTaskSubscriptions[taskId]?.abort();
                const controller = new AbortController();
                appInstance.moduleTaskSubscriptions[taskId] = controller;
                const handlers = typeof listener === 'function'
                    ? { onEvent: listener }
                    : (listener || {});

                (async () => {
                    let cursor = 0;
                    let failures = 0;
                    while (!controller.signal.aborted) {
                        try {
                            const response = await fetch(
                                `${taskPath(taskId)}/events`,
                                {
                                    headers: {
                                        'Last-Event-ID': String(cursor)
                                    },
                                    credentials: 'same-origin',
                                    signal: controller.signal
                                }
                            );
                            if (!response.ok || !response.body) {
                                let payload = null;
                                try {
                                    payload = await response.json();
                                } catch (_error) {}
                                throw new ModuleSdkError(
                                    payload?.detail || 'Module event stream failed',
                                    payload?.code || 'module_event_stream_failed',
                                    response.status
                                );
                            }
                            const reader = response.body
                                .pipeThrough(new TextDecoderStream())
                                .getReader();
                            let buffer = '';
                            while (!controller.signal.aborted) {
                                const { value, done } = await reader.read();
                                if (done) break;
                                buffer += value;
                                const blocks = buffer.split(/\r?\n\r?\n/);
                                buffer = blocks.pop() || '';
                                for (const block of blocks) {
                                    const event = parseSseBlock(block);
                                    if (!event || event.id <= cursor) continue;
                                    failures = 0;
                                    cursor = event.id;
                                    appInstance.applyModuleTaskEvent(taskId, event);
                                    if (
                                        event.event === 'artifact.added'
                                        || event.event === 'task.terminal'
                                    ) {
                                        const task = await moduleRequest(
                                            taskPath(taskId)
                                        );
                                        appInstance.upsertModuleTask(task);
                                        if (
                                            event.event === 'task.terminal'
                                            && task.chat_id
                                            && appInstance.currentChatId
                                                === task.chat_id
                                        ) {
                                            await appInstance.loadMessages(
                                                task.chat_id
                                            );
                                            await appInstance.loadChats();
                                        }
                                    }
                                    handlers.onEvent?.(event);
                                    if (
                                        event.event === 'task.terminal'
                                        || MODULE_TERMINAL_STATES.has(event.data?.state)
                                    ) {
                                        handlers.onClose?.();
                                        controller.abort();
                                        break;
                                    }
                                }
                            }
                            if (!controller.signal.aborted) {
                                throw new ModuleSdkError(
                                    'Module event stream ended before a terminal event',
                                    'module_event_stream_incomplete',
                                    0
                                );
                            }
                        } catch (error) {
                            if (controller.signal.aborted) break;
                            failures += 1;
                            handlers.onError?.(error);
                            if (failures >= 5) {
                                const taskView = appInstance.moduleTasks[taskId];
                                if (taskView) {
                                    taskView.error = error.message
                                        || 'Task updates unavailable';
                                }
                                break;
                            }
                            await new Promise(resolve => setTimeout(
                                resolve,
                                Math.min(500 * (2 ** (failures - 1)), 8000)
                            ));
                        }
                    }
                    if (appInstance.moduleTaskSubscriptions[taskId] === controller) {
                        delete appInstance.moduleTaskSubscriptions[taskId];
                    }
                })();

                return () => controller.abort();
            };

            const modulesSdk = Object.freeze({
                version: MODULE_SDK_VERSION,
                getFeatureStatus: moduleId => moduleRequest(
                    `/api/module-features/${encodeURIComponent(moduleId)}`
                ),
                startTask: async request => {
                    if (
                        !request
                        || typeof request.module_id !== 'string'
                        || typeof request.action_id !== 'string'
                        || !request.input
                        || typeof request.input !== 'object'
                        || Array.isArray(request.input)
                    ) {
                        throw new ModuleSdkError(
                            'module_id, action_id, and object input are required',
                            'invalid_sdk_argument',
                            0
                        );
                    }
                    const payload = {
                        module_id: request.module_id,
                        action_id: request.action_id,
                        input: request.input
                    };
                    for (const key of [
                        'chat_id',
                        'user_message',
                        'resource_ids'
                    ]) {
                        if (request[key] !== undefined) payload[key] = request[key];
                    }
                    const idempotencyKey = request.idempotency_key
                        || crypto.randomUUID();
                    const task = await moduleRequest('/api/module-tasks', {
                        method: 'POST',
                        headers: {
                            'Content-Type': 'application/json',
                            'Idempotency-Key': idempotencyKey
                        },
                        body: JSON.stringify(payload)
                    });
                    appInstance.rememberModuleTask(task.task_id);
                    appInstance.showModuleTask(task);
                    subscribe(task.task_id);
                    return task;
                },
                getTask: taskId => moduleRequest(taskPath(taskId)),
                subscribe,
                cancelTask: taskId => moduleRequest(
                    `${taskPath(taskId)}/cancel`,
                    {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: '{}'
                    }
                ),
                respondApproval: (taskId, approvalId, decision) => {
                    if (!['approve', 'deny'].includes(decision)) {
                        throw new ModuleSdkError(
                            'decision must be approve or deny',
                            'invalid_sdk_argument',
                            0
                        );
                    }
                    return moduleRequest(
                        `${taskPath(taskId)}/approvals/${encodeURIComponent(approvalId)}`,
                        {
                            method: 'POST',
                            headers: { 'Content-Type': 'application/json' },
                            body: JSON.stringify({ decision })
                        }
                    );
                },
                downloadArtifact: async (taskId, artifactRef) => {
                    const response = await fetch(
                        `${taskPath(taskId)}/artifacts/${encodeURIComponent(artifactRef)}`,
                        { credentials: 'same-origin' }
                    );
                    if (!response.ok) {
                        let payload = null;
                        try {
                            payload = await response.json();
                        } catch (_error) {}
                        throw new ModuleSdkError(
                            payload?.detail || 'Artifact download failed',
                            payload?.code || 'artifact_download_failed',
                            response.status
                        );
                    }
                    const disposition =
                        response.headers.get('content-disposition') || '';
                    const encoded = disposition.match(/filename\*=UTF-8''([^;]+)/i);
                    const fallback = disposition.match(/filename="([^"]+)"/i);
                    const filename = encoded
                        ? decodeURIComponent(encoded[1])
                        : (fallback?.[1] || 'artifact');
                    const url = URL.createObjectURL(await response.blob());
                    const anchor = document.createElement('a');
                    anchor.href = url;
                    anchor.download = filename;
                    anchor.click();
                    setTimeout(() => URL.revokeObjectURL(url), 0);
                    return { filename };
                }
            });
            window.ChatRaw = window.ChatRaw || {};
            window.ChatRaw.modules = modulesSdk;

            // Create global ChatRawPlugin object for plugins
            window.ChatRawPlugin = {
                // Hook system
                hooks: {
                    register: (hookName, handler) => this.registerHook(hookName, handler),
                    // List available hooks
                    available: () => Object.keys(this.pluginHooks)
                },
                
                // Dependency loader
                require: (depName) => this.loadedPluginDeps[depName],
                
                // Proxy API for external service calls
                proxy: {
                    // JSON request proxy
                    request: (params) => this.proxyRequest(params),
                    
                    // File upload proxy (for services like Whisper, OCR)
                    upload: async (file, serviceId, url, extraFields = {}, fileFieldName = 'file') => {
                        const formData = new FormData();
                        formData.append('file', file);
                        formData.append('service_id', serviceId);
                        formData.append('url', url);
                        formData.append('extra_fields', JSON.stringify(extraFields));
                        formData.append('file_field_name', fileFieldName);
                        
                        try {
                            const res = await fetch('/api/proxy/upload', {
                                method: 'POST',
                                body: formData
                            });
                            return await res.json();
                        } catch (e) {
                            return { success: false, error: e.message };
                        }
                    }
                },
                
                // Plugin settings
                settings: (pluginId) => this.getPluginSettings(pluginId || this._currentLoadingPlugin),

                // Composer input and completion APIs
                input: {
                    getValue: () => appInstance.inputMessage || '',
                    setValue: (value) => {
                        appInstance.setComposerValue(String(value || ''));
                        return true;
                    },
                    insertText: (text) => appInstance.insertComposerText(String(text || '')),
                    replaceRange: (start, end, text) => appInstance.replaceComposerRange(start, end, String(text || '')),
                    getSelection: () => appInstance.getComposerSelection(),
                    focus: () => {
                        appInstance.focusComposer();
                        return true;
                    },
                    registerCompletionProvider: (config, pluginIdOverride = null) => (
                        appInstance.registerCompletionProvider(config, pluginIdOverride)
                    ),
                    unregisterCompletionProvider: (id, pluginId = null) => (
                        appInstance.unregisterCompletionProvider(id, pluginId)
                    ),
                    invalidateSkillCatalog: () => appInstance.invalidateSkillCatalog()
                },
                
                // Utility functions for plugin developers
                utils: {
                    // Load external script dynamically
                    loadScript: (url) => appInstance.loadScript(url),
                    
                    // Load external CSS dynamically
                    loadCSS: (url) => appInstance.loadCSS(url),
                    
                    // Ensure highlight.js is loaded (for plugins that use hljs language packs)
                    loadHighlightJS: () => typeof loadHighlightJS === 'function' ? loadHighlightJS() : Promise.resolve(),
                    
                    // Show toast notification
                    showToast: (message, type = '') => appInstance.showToast(message, type),
                    
                    // Get current language
                    getLanguage: () => appInstance.lang,
                    
                    // Translate key (if exists in i18n)
                    t: (key) => appInstance.t(key),
                    
                    // Show progress indicator (uses existing upload progress)
                    showProgress: (percent, text = '') => {
                        appInstance.uploadProgress = {
                            show: true,
                            filename: text,
                            progress: percent,
                            status: 'processing',
                            current: percent,
                            total: 100
                        };
                    },
                    
                    // Hide progress indicator
                    hideProgress: () => {
                        appInstance.uploadProgress = {
                            show: false,
                            filename: '',
                            progress: 0,
                            status: '',
                            current: 0,
                            total: 0
                        };
                    },
                    
                    // Get current chat ID
                    getCurrentChatId: () => appInstance.currentChatId,
                    
                    // Get current messages
                    getMessages: () => [...appInstance.messages],
                    
                    // Add a message to the current chat display
                    addMessage: (role, content) => {
                        appInstance.messages.push({ role, content });
                        appInstance.$nextTick(() => appInstance.scrollToBottom());
                    }
                },
                
                // Plugin local storage (namespaced by plugin ID)
                // All methods accept an optional pluginId parameter for use after plugin loading
                storage: {
                    // Get value from plugin storage
                    // Usage: ChatRaw.storage.get(key, defaultValue, pluginId)
                    get: (key, defaultValue = null, pluginId = null) => {
                        const pid = pluginId || appInstance._currentLoadingPlugin;
                        if (!pid) {
                            console.warn('[Plugin Storage] No plugin context - pass pluginId as third argument');
                            return defaultValue;
                        }
                        try {
                            const storageKey = `chatraw_plugin_${pid}`;
                            const data = JSON.parse(localStorage.getItem(storageKey) || '{}');
                            return key in data ? data[key] : defaultValue;
                        } catch (e) {
                            return defaultValue;
                        }
                    },
                    
                    // Set value in plugin storage
                    // Usage: ChatRaw.storage.set(key, value, pluginId)
                    set: (key, value, pluginId = null) => {
                        const pid = pluginId || appInstance._currentLoadingPlugin;
                        if (!pid) {
                            console.warn('[Plugin Storage] No plugin context - pass pluginId as third argument');
                            return false;
                        }
                        try {
                            const storageKey = `chatraw_plugin_${pid}`;
                            const data = JSON.parse(localStorage.getItem(storageKey) || '{}');
                            data[key] = value;
                            // Limit storage size per plugin (1MB)
                            const serialized = JSON.stringify(data);
                            if (serialized.length > 1024 * 1024) {
                                console.warn('[Plugin Storage] Storage limit exceeded (1MB)');
                                return false;
                            }
                            localStorage.setItem(storageKey, serialized);
                            return true;
                        } catch (e) {
                            console.error('[Plugin Storage] Error:', e);
                            return false;
                        }
                    },
                    
                    // Remove key from plugin storage
                    // Usage: ChatRaw.storage.remove(key, pluginId)
                    remove: (key, pluginId = null) => {
                        const pid = pluginId || appInstance._currentLoadingPlugin;
                        if (!pid) return false;
                        try {
                            const storageKey = `chatraw_plugin_${pid}`;
                            const data = JSON.parse(localStorage.getItem(storageKey) || '{}');
                            delete data[key];
                            localStorage.setItem(storageKey, JSON.stringify(data));
                            return true;
                        } catch (e) {
                            return false;
                        }
                    },
                    
                    // Clear all plugin storage
                    // Usage: ChatRaw.storage.clear(pluginId)
                    clear: (pluginId = null) => {
                        const pid = pluginId || appInstance._currentLoadingPlugin;
                        if (!pid) return false;
                        try {
                            localStorage.removeItem(`chatraw_plugin_${pid}`);
                            return true;
                        } catch (e) {
                            return false;
                        }
                    },
                    
                    // Get all plugin storage data
                    // Usage: ChatRaw.storage.getAll(pluginId)
                    getAll: (pluginId = null) => {
                        const pid = pluginId || appInstance._currentLoadingPlugin;
                        if (!pid) return {};
                        try {
                            const storageKey = `chatraw_plugin_${pid}`;
                            return JSON.parse(localStorage.getItem(storageKey) || '{}');
                        } catch (e) {
                            return {};
                        }
                    }
                },
                
                // UI Extension API for toolbar buttons and fullscreen modal
                ui: {
                    // Register a toolbar button
                    // config: { id, icon, label, onClick, order? }, pluginId (optional)
                    registerToolbarButton: (config, pluginIdOverride = null) => {
                        const pluginId = pluginIdOverride || appInstance._currentLoadingPlugin || config.pluginId;
                        if (!pluginId) {
                            console.warn('[Plugin UI] Cannot register button: unknown plugin');
                            return false;
                        }
                        
                        // Validate icon format - must be RemixIcon (ri-xxx)
                        if (!config.icon || !/^ri-[a-z0-9-]+$/.test(config.icon)) {
                            console.warn(`[Plugin ${pluginId}] Invalid icon format. Must be RemixIcon (ri-xxx-xxx)`);
                            return false;
                        }
                        
                        if (!config.id || !config.onClick) {
                            console.warn(`[Plugin ${pluginId}] Button requires id and onClick`);
                            return false;
                        }
                        
                        const fullId = `${pluginId}:${config.id}`;
                        const existingIndex = appInstance.pluginToolbarButtons.findIndex(b => b.fullId === fullId);
                        
                        const buttonConfig = {
                            fullId,
                            pluginId,
                            id: config.id,
                            icon: config.icon,
                            label: config.label || { en: config.id },
                            onClick: config.onClick,
                            order: config.order ?? 100,
                            active: false,
                            loading: false
                        };
                        
                        if (existingIndex >= 0) {
                            // Update existing button
                            appInstance.pluginToolbarButtons[existingIndex] = buttonConfig;
                        } else {
                            // Add new button
                            appInstance.pluginToolbarButtons.push(buttonConfig);
                        }
                        
                        return true;
                    },
                    
                    // Unregister a toolbar button
                    unregisterToolbarButton: (buttonId, pluginId = null) => {
                        const pid = pluginId || appInstance._currentLoadingPlugin;
                        if (!pid) return false;
                        
                        const fullId = `${pid}:${buttonId}`;
                        const index = appInstance.pluginToolbarButtons.findIndex(b => b.fullId === fullId);
                        if (index >= 0) {
                            appInstance.pluginToolbarButtons.splice(index, 1);
                            return true;
                        }
                        return false;
                    },
                    
                    // Set button state (active/loading)
                    setButtonState: (buttonId, state, pluginId = null) => {
                        const pid = pluginId || appInstance._currentLoadingPlugin;
                        if (!pid) return false;
                        
                        const fullId = `${pid}:${buttonId}`;
                        const button = appInstance.pluginToolbarButtons.find(b => b.fullId === fullId);
                        if (button) {
                            if (state.active !== undefined) button.active = state.active;
                            if (state.loading !== undefined) button.loading = state.loading;
                            return true;
                        }
                        return false;
                    },
                    
                    // Open fullscreen modal
                    // options: { content, closable?, onClose? } or just HTML string, pluginId (optional)
                    openFullscreenModal: (options, pluginIdOverride = null) => {
                        const pluginId = pluginIdOverride || appInstance._currentLoadingPlugin || options?.pluginId;
                        
                        // Support simple string content
                        if (typeof options === 'string') {
                            options = { content: options };
                        }
                        
                        if (!options?.content) {
                            console.warn('[Plugin UI] Cannot open modal: empty content');
                            return false;
                        }
                        
                        appInstance.pluginFullscreenModal = {
                            show: true,
                            content: options.content,
                            closable: options.closable !== false,
                            onClose: options.onClose || null,
                            pluginId
                        };
                        return true;
                    },
                    
                    // Close fullscreen modal
                    closeFullscreenModal: () => {
                        appInstance.closePluginFullscreenModal();
                    }
                }
            };

            // Load enabled plugins
            this.loadEnabledPlugins();
        },
        
        // Load installed plugins list
        async loadInstalledPlugins() {
            try {
                const res = await fetch('/api/plugins');
                if (res.ok) {
                    this.installedPlugins = await res.json();
                }
            } catch (e) {
                console.error('Failed to load installed plugins:', e);
            }
        },
        
        // Load enabled plugins' JS
        async loadEnabledPlugins() {
            for (const plugin of this.installedPlugins) {
                if (plugin.enabled) {
                    await this.loadPluginJS(plugin);
                }
            }
        },
        
        // Load a plugin's JS file
        async loadPluginJS(plugin) {
            try {
                this.unregisterPluginHooks(plugin.id);
                this.unregisterPluginCompletions(plugin.id);
                this.pluginToolbarButtons = this.pluginToolbarButtons.filter(
                    button => button.pluginId !== plugin.id
                );
                if (this.pluginFullscreenModal?.pluginId === plugin.id) {
                    this.closePluginFullscreenModal();
                }

                // First load dependencies
                if (plugin.dependencies) {
                    for (const [name, url] of Object.entries(plugin.dependencies)) {
                        if (!this.loadedPluginDeps[name]) {
                            try {
                                // CSS must use loadCSS, not loadScript
                                if (typeof url === 'string' && url.endsWith('.css')) {
                                    await this.loadCSS(url);
                                    this.loadedPluginDeps[name] = true;
                                } else if (name.startsWith('hljs-')) {
                                    // hljs language packs loaded on-demand by plugin (need hljs core first)
                                    continue;
                                } else {
                                    await this.loadScript(url);
                                    // Common library detection patterns
                                    if (name === 'xlsx' && window.XLSX) {
                                        this.loadedPluginDeps[name] = window.XLSX;
                                    } else if (name === 'pdfjs' && window.pdfjsLib) {
                                        this.loadedPluginDeps[name] = window.pdfjsLib;
                                    } else if (window[name]) {
                                        this.loadedPluginDeps[name] = window[name];
                                    } else {
                                        this.loadedPluginDeps[name] = true;
                                    }
                                }
                            } catch (depError) {
                                console.error(`[Plugin] Failed to load dependency ${name} for ${plugin.id}:`, depError);
                                // Continue loading other dependencies
                            }
                        }
                    }
                }
                
                // Set current loading plugin for hook registration
                this._currentLoadingPlugin = plugin.id;
                
                // Then load the plugin main.js
                const scriptBaseUrl = `/api/plugins/${encodeURIComponent(plugin.id)}/main.js`;
                const pluginVersion = encodeURIComponent(String(plugin.version || '0'));
                const scriptUrl = `${scriptBaseUrl}?v=${pluginVersion}`;
                await this.loadScript(scriptUrl, { reload: true, reloadPrefix: scriptBaseUrl });
                
                this._currentLoadingPlugin = null;
                console.log(`[Plugin] Loaded: ${plugin.id}`);
            } catch (e) {
                this._currentLoadingPlugin = null;
                console.error(`[Plugin] Failed to load ${plugin.id}:`, e);
            }
        },
        
        // Load external script
        loadScript(url, options = {}) {
            return new Promise((resolve, reject) => {
                // Check if already loaded
                const existing = document.querySelector(`script[src="${url}"]`);
                if (existing) {
                    if (!options.reload) {
                        resolve();
                        return;
                    }
                    existing.remove();
                }
                if (options.reload && options.reloadPrefix) {
                    for (const script of Array.from(document.querySelectorAll('script'))) {
                        const src = script.getAttribute('src') || '';
                        if (src.startsWith(options.reloadPrefix)) {
                            script.remove();
                        }
                    }
                }
                
                const script = document.createElement('script');
                script.src = url;
                script.onload = resolve;
                script.onerror = () => reject(new Error(`Failed to load script: ${url}`));
                document.head.appendChild(script);
            });
        },
        
        loadCSS(url) {
            return new Promise((resolve, reject) => {
                const existing = document.querySelector(`link[href="${url}"]`);
                if (existing) {
                    resolve();
                    return;
                }
                const link = document.createElement('link');
                link.rel = 'stylesheet';
                link.href = url;
                link.onload = resolve;
                link.onerror = () => reject(new Error(`Failed to load CSS: ${url}`));
                document.head.appendChild(link);
            });
        },
        
        // Register a hook handler
        registerHook(hookName, handler) {
            if (!this.pluginHooks[hookName]) {
                console.warn(`[Plugin] Unknown hook: ${hookName}`);
                return;
            }
            
            // Add plugin ID to handler for tracking
            const pluginId = this._currentLoadingPlugin;
            const wrappedHandler = { ...handler, _pluginId: pluginId };
            
            this.pluginHooks[hookName].push(wrappedHandler);
            this.pluginHooks[hookName].sort((a, b) => (b.priority || 0) - (a.priority || 0));
            
            // Track for later removal
            if (pluginId) {
                if (!this.pluginHookRegistry[pluginId]) {
                    this.pluginHookRegistry[pluginId] = [];
                }
                this.pluginHookRegistry[pluginId].push({ hookName, handler: wrappedHandler });
            }
        },
        
        // Unregister all hooks for a plugin
        unregisterPluginHooks(pluginId) {
            const registrations = this.pluginHookRegistry[pluginId];
            if (!registrations) return;
            
            for (const { hookName, handler } of registrations) {
                const hooks = this.pluginHooks[hookName];
                if (hooks) {
                    const idx = hooks.indexOf(handler);
                    if (idx !== -1) {
                        hooks.splice(idx, 1);
                    }
                }
            }
            
            delete this.pluginHookRegistry[pluginId];
        },

        // Call pre-send interceptors. Only handled=true cancels the normal send path.
        async callSendInterceptors(context) {
            const handlers = this.pluginHooks.send_intercept || [];
            for (const handler of handlers) {
                if (handler._pluginId) {
                    const plugin = this.installedPlugins.find(p => p.id === handler._pluginId);
                    if (plugin && !plugin.enabled) continue;
                }

                try {
                    const result = await handler.handler(context);
                    if (result?.success && result.handled === true) return result;
                } catch (e) {
                    if (e?.name === 'AbortError') throw e;
                    console.error('[Hook send_intercept] Error:', e);
                }
            }
            return null;
        },
        
        // Call hook handlers
        async callHook(hookName, ...args) {
            const handlers = this.pluginHooks[hookName] || [];
            for (const handler of handlers) {
                // Skip if plugin is disabled
                if (handler._pluginId) {
                    const plugin = this.installedPlugins.find(p => p.id === handler._pluginId);
                    if (plugin && !plugin.enabled) continue;
                }
                
                try {
                    const result = await handler.handler(...args);
                    if (result?.success) return result;
                } catch (e) {
                    console.error(`[Hook ${hookName}] Error:`, e);
                }
            }
            return null;
        },
        
        // Get plugin settings with defaults
        getPluginSettings(pluginId) {
            const plugin = this.installedPlugins.find(p => p.id === pluginId);
            if (!plugin) return {};
            
            // Merge defaults with saved values
            const defaults = {};
            if (plugin.settings) {
                for (const setting of plugin.settings) {
                    defaults[setting.id] = setting.default;
                }
            }
            
            return { ...defaults, ...(plugin.settings_values || {}) };
        },
        
        // Proxy request for plugins
        async proxyRequest(params) {
            try {
                // Convert serviceId to service_id for backend compatibility
                const body = {
                    service_id: params.serviceId || params.service_id,
                    url: params.url,
                    method: params.method || 'POST',
                    headers: params.headers || {},
                    body: params.body || {}
                };
                
                const res = await fetch('/api/proxy/request', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(body)
                });
                return await res.json();
            } catch (e) {
                return { success: false, error: e.message };
            }
        },
        
        // Load plugin market
        async loadPluginMarket() {
            if (this.pluginMarketLoading) return;
            
            this.pluginMarketLoading = true;
            this.pluginMarketError = false;
            let timeout = null;
            
            try {
                const controller = new AbortController();
                timeout = setTimeout(() => controller.abort(), 5000);
                
                let res = await fetch('/api/plugins/market', { signal: controller.signal });
                if (!res.ok) {
                    res = await fetch(
                        'https://raw.githubusercontent.com/massif-01/ChatRaw/main/Plugins/Plugin_market/index.json',
                        { signal: controller.signal }
                    );
                }
                clearTimeout(timeout);
                timeout = null;
                
                if (!res.ok) throw new Error('Failed to fetch');
                
                const data = await res.json();
                this.marketPlugins = data.plugins || [];
            } catch (e) {
                if (e.name === 'AbortError') {
                    console.warn('Plugin market request timed out');
                } else {
                    console.error('Failed to load plugin market:', e);
                }
                this.pluginMarketError = true;
            } finally {
                if (timeout) clearTimeout(timeout);
                this.pluginMarketLoading = false;
            }
        },

        getMarketPluginIconUrl(plugin) {
            if (plugin?.id && this.isPluginInstalled(plugin.id)) {
                return `/api/plugins/${encodeURIComponent(plugin.id)}/icon`;
            }
            const folder = plugin?.folder || plugin?.id || '';
            return `/api/plugins/market/${encodeURIComponent(folder)}/icon`;
        },

        handleMarketPluginIconError(event, plugin) {
            const img = event?.target;
            if (!img) return;
            if (!img.dataset.remoteFallbackTried && plugin?.folder) {
                img.dataset.remoteFallbackTried = '1';
                img.src = `https://raw.githubusercontent.com/massif-01/ChatRaw/main/Plugins/Plugin_market/${plugin.folder}/icon.png`;
                return;
            }
            img.src = 'data:image/svg+xml,<svg xmlns=%22http://www.w3.org/2000/svg%22 viewBox=%220 0 24 24%22 fill=%22none%22 stroke=%22%23666%22 stroke-width=%222%22><path d=%22M14.7 6.3a1 1 0 0 0 0 1.4l1.6 1.6a1 1 0 0 0 1.4 0l3.77-3.77a6 6 0 0 1-7.94 7.94l-6.91 6.91a2.12 2.12 0 0 1-3-3l6.91-6.91a6 6 0 0 1 7.94-7.94l-3.76 3.76z%22/></svg>';
        },
        
        // Check if plugin is installed
        isPluginInstalled(pluginId) {
            return this.installedPlugins.some(p => p.id === pluginId);
        },
        
        // Filter market plugins by search (name + description, en + zh)
        get filteredMarketPlugins() {
            const q = (this.pluginMarketSearch || '').trim().toLowerCase();
            if (!q) return this.marketPlugins;
            return this.marketPlugins.filter(plugin => {
                const nameEn = (plugin.name?.en || '').toLowerCase();
                const nameZh = plugin.name?.zh || '';
                const descEn = (plugin.description?.en || '').toLowerCase();
                const descZh = plugin.description?.zh || '';
                return nameEn.includes(q) || nameZh.includes(q) || descEn.includes(q) || descZh.includes(q);
            });
        },
        
        // Install plugin from market
        async installPlugin(plugin) {
            this.pluginInstalling = plugin.id;
            
            try {
                const sourceUrl = `https://raw.githubusercontent.com/massif-01/ChatRaw/main/Plugins/Plugin_market/${plugin.folder}`;
                
                const res = await fetch('/api/plugins/install', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ source_url: sourceUrl })
                });
                
                const data = await res.json();
                
                if (data.success) {
                    this.showToast(this.t('installSuccess'), 'success');
                    await this.loadInstalledPlugins();
                    // Load the newly installed plugin
                    const newPlugin = this.installedPlugins.find(p => p.id === plugin.id);
                    if (newPlugin) {
                        await this.loadPluginJS(newPlugin);
                    }
                } else {
                    this.showToast(this.t('installFailed') + ': ' + data.error, 'error');
                }
            } catch (e) {
                this.showToast(this.t('installFailed') + ': ' + e.message, 'error');
            } finally {
                this.pluginInstalling = null;
            }
        },
        
        // Handle local plugin upload (from file input click)
        async handlePluginUpload(event) {
            const file = event.target?.files?.[0];
            if (!file) return;
            await this.uploadPluginFile(file, event.target);
        },
        
        // Handle plugin drop (from drag and drop)
        async handlePluginDrop(event) {
            const file = event.dataTransfer?.files?.[0];
            if (!file) return;
            event.dataTransfer.clearData();
            await this.uploadPluginFile(file);
        },
        
        async uploadPluginFile(file, fileInput) {
            if (!file.name.endsWith('.zip')) {
                this.showToast(this.t('onlyZipSupported'), 'error');
                return;
            }
            
            this.pluginUploading = true;
            
            try {
                const formData = new FormData();
                formData.append('file', file);
                
                const res = await fetch('/api/plugins/upload', {
                    method: 'POST',
                    body: formData
                });
                
                const data = await res.json();
                
                if (data.success) {
                    this.showToast(this.t('installSuccess'), 'success');
                    await this.loadInstalledPlugins();
                    const newPlugin = this.installedPlugins.find(p => p.id === data.plugin_id);
                    if (newPlugin) {
                        await this.loadPluginJS(newPlugin);
                    }
                } else {
                    this.showToast(this.t('installFailed') + ': ' + data.error, 'error');
                }
            } catch (e) {
                this.showToast(this.t('installFailed') + ': ' + e.message, 'error');
            } finally {
                this.pluginUploading = false;
                if (fileInput) fileInput.value = '';
            }
        },
        
        // Toggle plugin enabled/disabled
        async togglePlugin(plugin) {
            const newState = !plugin.enabled;
            
            try {
                const res = await fetch(`/api/plugins/${encodeURIComponent(plugin.id)}/toggle`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ enabled: newState })
                });
                
                if (res.ok) {
                    plugin.enabled = newState;
                    if (newState) {
                        // Load plugin if enabled
                        await this.loadPluginJS(plugin);
                        this.showToast(this.t('settingsSaved'), 'success');
                    } else {
                        // Unregister hooks when disabled
                        this.unregisterPluginHooks(plugin.id);
                        this.unregisterPluginCompletions(plugin.id);
                        
                        // Clean up toolbar buttons registered by this plugin
                        this.pluginToolbarButtons = this.pluginToolbarButtons.filter(
                            btn => btn.pluginId !== plugin.id
                        );
                        
                        // If this plugin has a fullscreen modal open, close it
                        if (this.pluginFullscreenModal.pluginId === plugin.id) {
                            this.closePluginFullscreenModal();
                        }
                        
                        this.showToast(this.t('pluginDisabled'), 'success');
                    }
                }
            } catch (e) {
                this.showToast(this.t('saveFailed'), 'error');
            }
        },
        
        // Open plugin settings
        async openPluginSettings(plugin) {
            this.currentPluginSettings = plugin;
            
            // Initialize settings with defaults, then override with saved values
            const settingsValues = {};
            if (plugin.settings) {
                for (const setting of plugin.settings) {
                    settingsValues[setting.id] = setting.default;
                }
            }
            // Override with saved values
            Object.assign(settingsValues, plugin.settings_values || {});
            
            this.pluginSettingsValues = settingsValues;
            this.pluginApiKeys = {};
            this.pluginApiKeyConfigured = {};
            this.pluginApiKeyActions = {};
            
            // Load saved API keys (masked) for display
            if (plugin.proxy && plugin.proxy.length > 0) {
                try {
                    const res = await fetch('/api/plugins/api-keys');
                    if (res.ok) {
                        const data = await res.json();
                        const savedKeys = data.api_keys || {};
                        for (const proxy of plugin.proxy) {
                            this.pluginApiKeys[proxy.id] = '';
                            this.pluginApiKeyConfigured[proxy.id] = Boolean(savedKeys[proxy.id]?.configured);
                            this.pluginApiKeyActions[proxy.id] = 'preserve';
                        }
                    }
                } catch (e) {
                    console.error('Failed to load API keys:', e);
                }
            }
            
            this.showPluginSettings = true;
            
            // Dispatch event for plugins with custom settings to inject their UI
            if (plugin.customSettings) {
                setTimeout(() => {
                    window.dispatchEvent(new CustomEvent('plugin-settings-open', {
                        detail: { pluginId: plugin.id, customSettings: true }
                    }));
                }, 50);
            }
        },
        
        // Save plugin settings
        async savePluginSettings() {
            if (!this.currentPluginSettings) return;
            
            try {
                // Save settings
                const settingsRes = await fetch(`/api/plugins/${encodeURIComponent(this.currentPluginSettings.id)}/settings`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ settings: this.pluginSettingsValues })
                });
                
                if (!settingsRes.ok) {
                    throw new Error('Failed to save settings');
                }
                
                // Save API keys (only if user entered a new value, not the masked placeholder)
                for (const [serviceId, apiKey] of Object.entries(this.pluginApiKeys)) {
                    const action = this.pluginApiKeyActions[serviceId] === 'clear'
                        ? 'clear'
                        : (apiKey ? 'replace' : 'preserve');
                    if (action !== 'preserve') {
                        await fetch('/api/plugins/api-key', {
                            method: 'POST',
                            headers: { 'Content-Type': 'application/json' },
                            body: JSON.stringify({ service_id: serviceId, api_key: apiKey, action })
                        });
                    }
                }
                
                // Update local state
                const plugin = this.installedPlugins.find(p => p.id === this.currentPluginSettings.id);
                if (plugin) {
                    plugin.settings_values = { ...this.pluginSettingsValues };
                }
                
                this.showPluginSettings = false;
                this.showToast(this.t('settingsSaved'), 'success');
            } catch (e) {
                this.showToast(this.t('saveFailed'), 'error');
            }
        },
        
        // Uninstall plugin
        async uninstallPlugin(plugin) {
            if (!plugin || !confirm(this.t('confirmUninstall'))) return;
            
            try {
                // First unregister hooks
                this.unregisterPluginHooks(plugin.id);
                this.unregisterPluginCompletions(plugin.id);
                
                // Clean up toolbar buttons registered by this plugin
                this.pluginToolbarButtons = this.pluginToolbarButtons.filter(
                    btn => btn.pluginId !== plugin.id
                );
                
                // If this plugin has a fullscreen modal open, close it
                if (this.pluginFullscreenModal.pluginId === plugin.id) {
                    this.closePluginFullscreenModal();
                }
                
                const res = await fetch(`/api/plugins/${encodeURIComponent(plugin.id)}`, {
                    method: 'DELETE'
                });
                
                if (res.ok) {
                    this.showPluginSettings = false;
                    this.currentPluginSettings = null;
                    this.showToast(this.t('uninstallSuccess'), 'success');
                    await this.loadInstalledPlugins();
                } else {
                    const data = await res.json().catch(() => ({}));
                    this.showToast(this.t('uninstallFailed') + (data.error ? ': ' + data.error : ''), 'error');
                }
            } catch (e) {
                this.showToast(this.t('uninstallFailed'), 'error');
            }
        }
    };
}
