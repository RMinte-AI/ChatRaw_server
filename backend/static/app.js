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
        appDocumentTitle: '{brand} Workspace',
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
        close: 'Close',
        online: 'Online',
        signOut: 'Sign out',
        featureCategories: 'Feature categories',
        featureNavigation: 'Feature navigation',
        loadingFeatureCatalog: 'Loading feature catalog…',
        noFeatures: 'No features available',
        openFeature: 'Open',
        featureUnavailable: 'Unavailable',
        featureAvailable: 'Available',
        featureLoading: 'Loading',
        moduleUnavailable: 'Module unavailable',
        pluginMissing: 'Plugin missing',
        pluginDisabledState: 'Plugin disabled',
        pluginVersionMismatch: 'Plugin version mismatch',
        panelNotRegistered: 'Panel not registered',
        mainPlacementRequired: 'Main view required',
        featurePanelNotReady: 'The feature panel is not ready.',
        backHome: 'Back to home',
        currentConversation: 'Current conversation',
        agentSubtitle: 'Your intelligent work assistant',
        conversationHistory: 'Conversation history',
        newConversation: 'New conversation',
        closeAgent: 'Close Agent',
        openAgent: 'Open Hermes Agent',
        expandAgent: 'Expand conversation window',
        restoreAgent: 'Restore conversation window',
        renameConversation: 'Rename conversation',
        deleteConversation: 'Delete conversation',
        noConversationHistory: 'No conversation history yet'
    },
    zh: {
        appDocumentTitle: '{brand} 工作空间',
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
        close: '关闭',
        online: '在线',
        signOut: '退出登录',
        featureCategories: '功能分类',
        featureNavigation: '功能导航',
        loadingFeatureCatalog: '正在读取功能目录…',
        noFeatures: '暂无功能',
        openFeature: '打开',
        featureUnavailable: '暂不可用',
        featureAvailable: '可用',
        featureLoading: '加载中',
        moduleUnavailable: '模块不可用',
        pluginMissing: '插件未安装',
        pluginDisabledState: '插件已停用',
        pluginVersionMismatch: '插件版本不兼容',
        panelNotRegistered: '功能面板未注册',
        mainPlacementRequired: '需要主内容区布局',
        featurePanelNotReady: '功能界面尚未就绪。',
        backHome: '返回首页',
        currentConversation: '当前对话',
        agentSubtitle: '你的智能工作助手',
        conversationHistory: '历史会话',
        newConversation: '新建会话',
        closeAgent: '关闭 Agent',
        openAgent: '打开 Hermes Agent',
        expandAgent: '扩展对话窗口',
        restoreAgent: '还原对话窗口',
        renameConversation: '重命名会话',
        deleteConversation: '删除会话',
        noConversationHistory: '还没有历史会话'
    }
};

Object.assign(i18n.en, {
    send: 'Send',
    rename: 'Rename',
    renameSharedChat: 'Rename this conversation',
    renameFailed: 'Rename failed',
    deleteSharedChat: 'Delete this private conversation? This cannot be undone.',
    deleteSharedDocument: 'Delete this shared document? Other users will lose access to it.',
    requestFailed: 'Request failed',
    unknownError: 'Unknown error',
    authenticationRequired: 'Authentication required',
    settingsNavigation: 'Settings navigation',
    pluginNavigation: 'Plugin navigation',
    preview: 'Preview',
    logoAlt: 'Logo',
    userAvatarAlt: 'User avatar',
    assistantAvatarAlt: 'AI assistant avatar',
    artifactSize: '{size} bytes',
    removeImage: 'Remove image',
    removeUrl: 'Remove URL',
    removeDocument: 'Remove document',
    removeLogo: 'Remove logo',
    composerSuggestions: 'Composer suggestions',
    apiEndpoint: 'API Endpoint',
    apiKeyOptional: 'API Key (Optional)',
    configuredReplace: 'Configured — enter to replace',
    clearKey: 'Clear key',
    modelId: 'Model ID',
    temperature: 'Temperature',
    topP: 'Top P',
    english: 'English',
    chinese: '中文',
    users: 'Users',
    userManagement: 'User management',
    userManagementDesc: 'Create accounts, control access, and reset passwords. Usernames cannot be changed.',
    username: 'Username',
    initialPassword: 'Initial password',
    role: 'Role',
    member: 'Member',
    administrator: 'Administrator',
    createUser: 'Create user',
    resetPassword: 'Reset password',
    enable: 'Enable',
    disable: 'Disable',
    enabled: 'Enabled',
    disabled: 'Disabled',
    userCreated: 'User created',
    userUpdated: 'User updated',
    passwordReset: 'Password reset; existing sessions revoked',
    newPasswordFor: 'New password for {username}',
    unableCreateUser: 'Unable to create user',
    unableUpdateUser: 'Unable to update user',
    unableResetPassword: 'Unable to reset password',
    unableChangePassword: 'Unable to change password',
    modules: 'Modules',
    featureSuites: 'Feature suites',
    featureSuitesDesc: 'Each product feature joins one backend module with either a companion plugin or a source-built Resident Integration. ChatRaw does not start processes or containers.',
    composeNetwork: 'Compose network',
    composeNetworkDesc: 'Use this network for ChatRaw and module services.',
    containerAddressRepair: 'Container address repair required',
    addressesUnchanged: 'Existing addresses were not changed automatically.',
    moduleAddress: 'Module address',
    moduleAddressSecret: 'The address is sent to ChatRaw once and is never returned by the management API.',
    pairingCode: 'One-time pairing code',
    connectForReview: 'Connect for review',
    noModules: 'No modules are connected.',
    moduleId: 'Module ID',
    frontendIntegration: 'Frontend integration',
    moduleProtocol: 'Module protocol',
    installedVersion: 'Installed version',
    requires: 'Requires',
    residentSourceBuilt: 'Resident Integration is source-built into this ChatRaw deployment.',
    networkAndConfiguration: 'Network and configuration',
    configurationStatus: 'Configuration',
    lastChecked: 'Last checked',
    dataOwnership: 'Data ownership and retention',
    requestedCapabilities: 'Requested host capabilities',
    none: 'None.',
    recentFault: 'Current availability issue',
    declaredActions: 'Declared actions',
    noActions: 'No actions declared.',
    minimumRole: 'minimum role',
    supportsStream: 'stream',
    supportsCancel: 'cancel',
    supportsApproval: 'approval',
    supportsArtifacts: 'artifacts',
    supportsChatProjection: 'chat projection',
    reviewRequired: 'Review is required before this module can be enabled.',
    requirementsIncomplete: 'Approved, but health, configuration, Ready, or frontend integration requirements are incomplete.',
    approveDeclaration: 'Approve declaration',
    checkHealth: 'Check health',
    refreshManifest: 'Refresh manifest',
    configure: 'Configure',
    enableSuite: 'Enable suite',
    drain: 'Drain',
    purgeModuleData: 'Purge module data',
    disconnect: 'Disconnect',
    moduleConfiguration: 'Module configuration',
    keep: 'Keep',
    replace: 'Replace',
    clear: 'Clear',
    newSecret: 'New secret',
    saveModuleConfiguration: 'Save module configuration',
    moduleOperationFailed: 'Module operation failed',
    modulePaired: 'Module paired for review',
    approveModuleConfirm: 'Approve {moduleId} and its declared capabilities?',
    moduleApproved: 'Module manifest approved',
    moduleActionCompleted: 'Module {action} completed',
    configurationSavedRevision: 'Configuration saved at revision {revision}',
    disconnectModulePrompt: 'Type {moduleId} to disconnect. Module data will be preserved.',
    moduleDisconnected: 'Module disconnected; module data was preserved',
    purgeModulePrompt: 'This deletes data owned by the module. Type {confirmation} to continue.',
    moduleDataPurged: 'Module-owned data purged',
    actionCheck: 'check',
    actionRefresh: 'refresh',
    actionEnable: 'enable',
    actionDrain: 'drain',
    actionDisable: 'disable',
    account: 'Account',
    currentPassword: 'Current password',
    newPassword: 'New password',
    changePassword: 'Change password',
    signOut: 'Sign out',
    loading: 'Loading...',
    pluginInfo: 'Plugin info',
    installPlugin: 'Install plugin',
    closeResidentIntegration: 'Close Resident Integration',
    tasks: 'Tasks',
    moduleTask: 'Module task',
    task: 'Task',
    closeTask: 'Close task',
    moduleTasks: 'Module tasks',
    approvalRequired: 'Approval required',
    taskProgress: 'Task progress',
    approve: 'Approve',
    deny: 'Deny',
    output: 'Output',
    artifacts: 'Artifacts',
    cancelTask: 'Cancel task',
    executionProcess: 'Execution process',
    activityRunning: 'Running',
    activityUpdated: 'Updated',
    activityInterrupted: 'Previous run did not finish',
    waitingForExecutionDetails: 'Waiting for execution details',
    noExecutionDetails: 'No execution details were retained',
    tool: 'Tool',
    viewDetails: 'View details',
    toolInput: 'Input',
    toolResult: 'Result',
    resultInConversation: 'This task is displayed in its conversation.',
    statePending: 'Pending',
    stateQueued: 'Queued',
    statePaired: 'Paired',
    stateReviewRequired: 'Review required',
    stateApproved: 'Approved',
    stateEnabled: 'Enabled',
    stateDisabled: 'Disabled',
    stateDraining: 'Draining',
    stateReady: 'Ready',
    stateHealthy: 'Healthy',
    stateUnhealthy: 'Unhealthy',
    stateConfigured: 'Configured',
    stateUnconfigured: 'Not configured',
    stateRunning: 'Running',
    stateSucceeded: 'Succeeded',
    stateFailed: 'Failed',
    stateCancelled: 'Cancelled',
    statePendingApproval: 'Pending approval',
    stateReachable: 'Reachable',
    stateUnreachable: 'Unreachable',
    stateCompatible: 'Compatible',
    stateIncompatible: 'Incompatible',
    statePresent: 'Present',
    stateMissing: 'Missing',
    stateValid: 'Valid',
    stateInvalid: 'Invalid',
    statePlugin: 'Plugin',
    stateResident: 'Resident Integration',
    stateInstalled: 'Installed',
    stateAvailable: 'Available',
    stateUnknown: 'Unknown',
    invalidRequest: 'Invalid request',
    invalidUsernameType: 'Username must be text',
    invalidUsernameLength: 'Username length is invalid',
    invalidUsernameCharacters: 'Username contains unsupported characters',
    invalidPasswordLength: 'Password is too short',
    invalidPasswordTooLong: 'Password is too long',
    setupUnavailable: 'Initial setup is unavailable',
    usernameInUse: 'Username is already in use',
    invalidCredentials: 'Invalid username or password',
    currentPasswordIncorrect: 'Current password is incorrect',
    invalidRole: 'Invalid role',
    userNotFound: 'User not found',
    lastActiveAdmin: 'The last active administrator cannot be disabled',
    administratorRequired: 'Administrator permission is required',
    selfUserManagementForbidden: 'Manage your own password from Account; your role and access cannot be changed here',
    confirmPassword: 'Confirm password',
    passwordsDoNotMatch: 'The passwords do not match',
    passwordMinimum: 'Use at least 12 characters',
    administratorAccessWarning: 'Administrators can manage users, models, plugins, and modules.',
    usersLoading: 'Loading users…',
    usersEmpty: 'No users found.',
    usersLoadFailed: 'Unable to load users. Try again.',
    createdAt: 'Created',
    updatedAt: 'Updated',
    currentUser: 'You',
    promoteAdministrator: 'Promote to administrator',
    demoteMember: 'Change to member',
    confirmPromoteUser: 'Promote {username} to administrator? They will gain all management permissions and must sign in again.',
    confirmDemoteUser: 'Change {username} to member? They will lose management permissions and must sign in again.',
    confirmDisableUser: 'Disable {username}? Their sessions and task capabilities will be revoked; their data will be kept.',
    userRoleUpdated: 'User role updated',
    resetPasswordTitle: 'Reset password',
    resetPasswordDesc: 'Set a new password for {username}. Their existing sessions will be revoked.',
    savePassword: 'Save password',
    cancel: 'Cancel',
    manageSelfInAccount: 'Use Account to change your own password.',
    unavailable: 'Unavailable',
    risk: 'risk',
    taskScoped: 'task-scoped',
    declarationOnly: 'declaration only',
    revision: 'Revision',
    secretConfigured: 'Secret configured',
    secretNotConfigured: 'Secret not configured',
    notCheckedYet: 'Not checked yet',
    taskFailed: 'Task failed',
    taskInProgress: 'Task in progress',
    taskUpdatesUnavailable: 'Task updates unavailable'
});

Object.assign(i18n.zh, {
    send: '发送',
    rename: '重命名',
    renameSharedChat: '重命名此会话',
    renameFailed: '重命名失败',
    deleteSharedChat: '确定删除此私有会话吗？此操作无法撤销。',
    deleteSharedDocument: '确定删除此共享文档吗？其他用户将无法再访问。',
    requestFailed: '请求失败',
    unknownError: '未知错误',
    authenticationRequired: '需要登录',
    settingsNavigation: '设置导航',
    pluginNavigation: '插件导航',
    preview: '预览',
    logoAlt: 'Logo',
    userAvatarAlt: '用户头像',
    assistantAvatarAlt: 'AI 助手头像',
    artifactSize: '{size} 字节',
    removeImage: '移除图片',
    removeUrl: '移除网址',
    removeDocument: '移除文档',
    removeLogo: '移除 Logo',
    composerSuggestions: '输入建议',
    apiEndpoint: 'API 地址',
    apiKeyOptional: 'API 密钥（可选）',
    configuredReplace: '已配置 — 输入新值可替换',
    clearKey: '清除密钥',
    modelId: '模型 ID',
    temperature: '温度',
    topP: 'Top P',
    english: 'English',
    chinese: '中文',
    users: '用户',
    userManagement: '用户管理',
    userManagementDesc: '创建账户、控制访问权限并重置密码。用户名不可修改。',
    username: '用户名',
    initialPassword: '初始密码',
    role: '角色',
    member: '普通用户',
    administrator: '管理员',
    createUser: '创建用户',
    resetPassword: '重置密码',
    enable: '启用',
    disable: '停用',
    enabled: '已启用',
    disabled: '已停用',
    userCreated: '用户已创建',
    userUpdated: '用户状态已更新',
    passwordReset: '密码已重置，已有会话已撤销',
    newPasswordFor: '为 {username} 设置新密码',
    unableCreateUser: '无法创建用户',
    unableUpdateUser: '无法更新用户',
    unableResetPassword: '无法重置密码',
    unableChangePassword: '无法修改密码',
    modules: '模块',
    featureSuites: '功能套件',
    featureSuitesDesc: '每项产品功能由一个后端模块与配套插件或源码内置的 Resident Integration 组成。ChatRaw 不负责启动进程或容器。',
    composeNetwork: 'Compose 网络',
    composeNetworkDesc: 'ChatRaw 与模块服务应使用此网络。',
    containerAddressRepair: '需要修复容器地址',
    addressesUnchanged: '现有地址不会被自动修改。',
    moduleAddress: '模块地址',
    moduleAddressSecret: '该地址仅向 ChatRaw 提交一次，管理 API 不会返回此地址。',
    pairingCode: '一次性配对码',
    connectForReview: '连接并进入审核',
    noModules: '尚未连接模块。',
    moduleId: '模块 ID',
    frontendIntegration: '前端集成',
    moduleProtocol: '模块协议',
    installedVersion: '已安装版本',
    requires: '要求',
    residentSourceBuilt: 'Resident Integration 已随当前 ChatRaw 部署从源码构建。',
    networkAndConfiguration: '网络与配置',
    configurationStatus: '配置',
    lastChecked: '上次检查',
    dataOwnership: '数据所有权与保留',
    requestedCapabilities: '申请的主机能力',
    none: '无。',
    recentFault: '当前不可用原因',
    declaredActions: '声明的操作',
    noActions: '未声明操作。',
    minimumRole: '最低角色',
    supportsStream: '流式',
    supportsCancel: '可取消',
    supportsApproval: '需审批',
    supportsArtifacts: '产物',
    supportsChatProjection: '投影到对话',
    reviewRequired: '必须先审核此模块，才能启用。',
    requirementsIncomplete: '已批准，但健康检查、配置、Ready 状态或前端集成要求尚未满足。',
    approveDeclaration: '批准声明',
    checkHealth: '检查健康状态',
    refreshManifest: '刷新清单',
    configure: '配置',
    enableSuite: '启用套件',
    drain: '排空',
    purgeModuleData: '清除模块数据',
    disconnect: '断开连接',
    moduleConfiguration: '模块配置',
    keep: '保留',
    replace: '替换',
    clear: '清除',
    newSecret: '新密钥',
    saveModuleConfiguration: '保存模块配置',
    moduleOperationFailed: '模块操作失败',
    modulePaired: '模块已连接，等待审核',
    approveModuleConfirm: '批准 {moduleId} 及其声明的能力吗？',
    moduleApproved: '模块清单已批准',
    moduleActionCompleted: '模块{action}操作已完成',
    configurationSavedRevision: '配置已保存，修订版本 {revision}',
    disconnectModulePrompt: '输入 {moduleId} 以断开连接。模块数据将保留。',
    moduleDisconnected: '模块已断开连接，模块数据已保留',
    purgeModulePrompt: '这会删除模块拥有的数据。输入 {confirmation} 继续。',
    moduleDataPurged: '模块数据已清除',
    actionCheck: '检查',
    actionRefresh: '刷新',
    actionEnable: '启用',
    actionDrain: '排空',
    actionDisable: '停用',
    account: '账户',
    currentPassword: '当前密码',
    newPassword: '新密码',
    changePassword: '修改密码',
    signOut: '退出登录',
    loading: '加载中...',
    pluginInfo: '插件信息',
    installPlugin: '安装插件',
    closeResidentIntegration: '关闭 Resident Integration',
    tasks: '任务',
    moduleTask: '模块任务',
    task: '任务',
    closeTask: '关闭任务',
    moduleTasks: '模块任务',
    approvalRequired: '需要审批',
    taskProgress: '任务进度',
    approve: '批准',
    deny: '拒绝',
    output: '输出',
    artifacts: '产物',
    cancelTask: '取消任务',
    executionProcess: '执行过程',
    activityRunning: '运行中',
    activityUpdated: '已更新',
    activityInterrupted: '上次执行未完成',
    waitingForExecutionDetails: '正在等待执行详情',
    noExecutionDetails: '没有保留执行详情',
    tool: '工具',
    viewDetails: '查看详情',
    toolInput: '输入',
    toolResult: '结果',
    resultInConversation: '此任务已在对应对话中展示。',
    statePending: '等待中',
    stateQueued: '排队中',
    statePaired: '已配对',
    stateReviewRequired: '等待审核',
    stateApproved: '已批准',
    stateEnabled: '已启用',
    stateDisabled: '已停用',
    stateDraining: '排空中',
    stateReady: '就绪',
    stateHealthy: '健康',
    stateUnhealthy: '异常',
    stateConfigured: '已配置',
    stateUnconfigured: '未配置',
    stateRunning: '运行中',
    stateSucceeded: '已成功',
    stateFailed: '失败',
    stateCancelled: '已取消',
    statePendingApproval: '等待审批',
    stateReachable: '可访问',
    stateUnreachable: '无法访问',
    stateCompatible: '兼容',
    stateIncompatible: '不兼容',
    statePresent: '已存在',
    stateMissing: '缺失',
    stateValid: '有效',
    stateInvalid: '无效',
    statePlugin: '插件',
    stateResident: 'Resident Integration',
    stateInstalled: '已安装',
    stateAvailable: '可用',
    stateUnknown: '未知',
    invalidRequest: '请求无效',
    invalidUsernameType: '用户名必须是文本',
    invalidUsernameLength: '用户名长度不符合要求',
    invalidUsernameCharacters: '用户名包含不支持的字符',
    invalidPasswordLength: '密码长度不足',
    invalidPasswordTooLong: '密码过长',
    setupUnavailable: '初始设置当前不可用',
    usernameInUse: '用户名已被使用',
    invalidCredentials: '用户名或密码错误',
    currentPasswordIncorrect: '当前密码错误',
    invalidRole: '角色无效',
    userNotFound: '未找到用户',
    lastActiveAdmin: '不能停用最后一名活跃管理员',
    administratorRequired: '需要管理员权限',
    selfUserManagementForbidden: '请在“账户”中修改自己的密码；不能在此变更自己的角色或访问状态',
    confirmPassword: '确认密码',
    passwordsDoNotMatch: '两次输入的密码不一致',
    passwordMinimum: '密码至少 12 个字符',
    administratorAccessWarning: '管理员可以管理用户、模型、插件和模块。',
    usersLoading: '正在加载用户…',
    usersEmpty: '没有找到用户。',
    usersLoadFailed: '无法加载用户，请重试。',
    createdAt: '创建时间',
    updatedAt: '更新时间',
    currentUser: '当前账户',
    promoteAdministrator: '提升为管理员',
    demoteMember: '降为普通用户',
    confirmPromoteUser: '确定将 {username} 提升为管理员吗？该用户将获得全部管理权限，并需要重新登录。',
    confirmDemoteUser: '确定将 {username} 降为普通用户吗？该用户将失去管理权限，并需要重新登录。',
    confirmDisableUser: '确定停用 {username} 吗？其会话和任务能力将立即撤销，但数据会保留。',
    userRoleUpdated: '用户角色已更新',
    resetPasswordTitle: '重置密码',
    resetPasswordDesc: '为 {username} 设置新密码。该用户已有会话将立即失效。',
    savePassword: '保存密码',
    cancel: '取消',
    manageSelfInAccount: '请在“账户”中修改自己的密码。',
    unavailable: '不可用',
    risk: '风险',
    taskScoped: '仅任务范围',
    declarationOnly: '仅声明',
    revision: '修订版本',
    secretConfigured: '密钥已配置',
    secretNotConfigured: '密钥未配置',
    notCheckedYet: '尚未检查',
    taskFailed: '任务失败',
    taskInProgress: '任务进行中',
    taskUpdatesUnavailable: '任务更新暂不可用'
});

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

const SKILL_MANAGER_PLUGIN_ID = 'skill-manager';
const COMPOSER_COMPLETION_LIMIT = 20;
const SKILL_CATALOG_CACHE_MS = 30000;
const MAX_ACTIVE_SKILLS_PER_REQUEST = 5;
const AGENT_CHAT_ENDPOINT = '/api/agent/chat';
const RESERVED_SLASH_COMMANDS = new Set(['plugins', 'settings', 'help', 'clear', 'compact', 'api']);
const COMMON_PATH_ROOTS = new Set(['tmp', 'var', 'usr', 'etc', 'home', 'users', 'opt', 'private', 'volumes', 'mnt']);
const SKILL_NAME_PATTERN = /^[a-z0-9](?:[a-z0-9-]{0,62}[a-z0-9])?$/;
const MODULE_SDK_VERSION = '1.6.0';
const MODULE_TASK_STORAGE_KEY = 'chatraw_module_tasks_v1';
const MODULE_TERMINAL_STATES = new Set(['succeeded', 'failed', 'cancelled']);
const PLUGIN_WORKSPACE_PLACEMENTS = Object.freeze([
    'right',
    'top',
    'bottom',
    'main'
]);
const PLUGIN_WORKSPACE_PANEL_ID_PATTERN = /^[a-z0-9](?:[a-z0-9._-]{0,62}[a-z0-9])?$/;
const MODULE_ACTIVITY_LIMIT = 512;

function app() {
    return {
        // Language
        lang: localStorage.getItem('justchat_lang') || 'en',
        
        // State
        showSettings: false,
        agentOpen: false,
        agentExpanded: false,
        agentHistoryOpen: false,
        featureCatalog: { categories: [], cards: [] },
        activeFeatureCategory: 'data-hub',
        featureCatalogLoading: true,
        settingsTab: 'models',
        me: null,
        adminUsers: [],
        adminUsersLoading: false,
        adminUsersError: null,
        adminCreateBusy: false,
        adminUserBusy: {},
        newUser: {
            username: '',
            password: '',
            confirmPassword: '',
            role: 'member'
        },
        resetUserPasswordDialog: {
            show: false,
            user: null,
            newPassword: '',
            confirmPassword: ''
        },
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
        residentIntegrations: [],
        residentBuiltIntegrationIds: [],
        residentIntegrationDefinitions: {},
        residentRegistrationOpen: false,
        residentWorkspace: {
            show: false,
            integrationId: null,
            title: '',
            error: null,
            cleanup: null
        },
        _residentFocusHandler: null,
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
        pluginToolbarButtons: [],  // Generic plugin entries for the Agent composer toolbar.
        showPluginMoreMenu: false,
        pluginFullscreenModal: {
            show: false,
            content: '',
            closable: true,
            onClose: null,
            pluginId: null
        },
        pluginWorkspaceDefinitions: {},
        pluginWorkspace: {
            show: false,
            pluginId: null,
            panelId: null,
            title: null,
            icon: '',
            collectionId: null,
            collectionTitle: null,
            collectionIcon: '',
            placement: null,
            dispose: null
        },
        _pluginWorkspaceReturnFocus: null,
        _pluginWorkspaceActivation: null,
        _pluginWorkspaceTransition: null,
        _rootWheelHandler: null,
        
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
        pluginRuntimeVersions: {},
        _pluginRuntimeSyncPromise: null,
        _pluginRuntimeSyncInitialized: false,
        _pluginRuntimeChangeChannel: null,
        _agentChatChangeChannel: null,
        _settingsChangeChannel: null,
        
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
        t(key, params = {}) {
            const dictionary = i18n[this.lang] || i18n.en;
            const template = dictionary[key] ?? i18n.en[key] ?? key;
            return String(template).replace(/\{(\w+)\}/g, (_match, name) => (
                params[name] === undefined ? `{${name}}` : String(params[name])
            ));
        },
        
        // Set language
        setLanguage(newLang) {
            this.lang = newLang === 'zh' ? 'zh' : 'en';
            localStorage.setItem('justchat_lang', this.lang);
            document.documentElement.lang = this.lang === 'zh' ? 'zh-CN' : 'en';
            this.updateDocumentTitle();
        },

        updateDocumentTitle() {
            const brand = this.settings?.ui_settings?.logo_text || 'ChatRaw';
            document.title = this.t('appDocumentTitle', { brand });
        },

        roleLabel(role) {
            return this.t(role === 'admin' ? 'administrator' : 'member');
        },

        stateLabel(state) {
            const normalized = String(state ?? '').trim().toLowerCase().replace(/[\s-]+/g, '_');
            const keys = {
                pending: 'statePending',
                queued: 'stateQueued',
                paired: 'statePaired',
                review_required: 'stateReviewRequired',
                pending_review: 'stateReviewRequired',
                approved: 'stateApproved',
                enabled: 'stateEnabled',
                disabled: 'stateDisabled',
                draining: 'stateDraining',
                ready: 'stateReady',
                healthy: 'stateHealthy',
                unhealthy: 'stateUnhealthy',
                configured: 'stateConfigured',
                unconfigured: 'stateUnconfigured',
                running: 'stateRunning',
                succeeded: 'stateSucceeded',
                completed: 'stateSucceeded',
                failed: 'stateFailed',
                cancelled: 'stateCancelled',
                canceled: 'stateCancelled',
                pending_approval: 'statePendingApproval',
                reachable: 'stateReachable',
                unreachable: 'stateUnreachable',
                compatible: 'stateCompatible',
                incompatible: 'stateIncompatible',
                present: 'statePresent',
                missing: 'stateMissing',
                valid: 'stateValid',
                invalid: 'stateInvalid',
                plugin: 'statePlugin',
                resident: 'stateResident',
                installed: 'stateInstalled',
                available: 'stateAvailable',
                unavailable: 'unavailable',
                not_present: 'stateMissing'
            };
            return keys[normalized] ? this.t(keys[normalized]) : (state || this.t('stateUnknown'));
        },

        actionLabel(action) {
            const key = {
                check: 'actionCheck',
                refresh: 'actionRefresh',
                enable: 'actionEnable',
                drain: 'actionDrain',
                disable: 'actionDisable'
            }[action];
            return key ? this.t(key) : action;
        },

        localizeError(error, fallbackKey = 'requestFailed') {
            const code = typeof error === 'string'
                ? error
                : error?.code || error?.error?.code || error?.detail?.code;
            const keys = {
                invalid_request: 'invalidRequest',
                invalid_username_type: 'invalidUsernameType',
                invalid_username_length: 'invalidUsernameLength',
                invalid_username_characters: 'invalidUsernameCharacters',
                invalid_password_length: 'invalidPasswordLength',
                invalid_password_too_long: 'invalidPasswordTooLong',
                setup_unavailable: 'setupUnavailable',
                username_in_use: 'usernameInUse',
                invalid_credentials: 'invalidCredentials',
                current_password_incorrect: 'currentPasswordIncorrect',
                invalid_role: 'invalidRole',
                user_not_found: 'userNotFound',
                last_active_admin: 'lastActiveAdmin',
                administrator_required: 'administratorRequired',
                self_user_management_forbidden: 'selfUserManagementForbidden',
                task_failed: 'taskFailed',
                module_event_stream_failed: 'taskUpdatesUnavailable',
                module_event_stream_incomplete: 'taskUpdatesUnavailable'
            };
            if (keys[code]) return this.t(keys[code]);
            return this.t(fallbackKey);
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
            this.setLanguage(this.lang);
            this.installRootWheelGuard();
            await this.loadMe();
            await this.loadSettings();
            await this.loadModels();
            await this.loadAgentChats();
            await this.loadFeatureCatalog();
            await this.loadDocuments();
            await this.loadInstalledPlugins();
            this.applyTheme();
            this.initCrossTabStateSync();
            // Note: favicon is updated by loadLogo() which is called from loadSettings()
            // Initialize plugin system
            this.initPluginSystem();
            await this.initResidentIntegrations();
            await this.resumeModuleTasks();
        },

        initCrossTabStateSync() {
            if (typeof window.BroadcastChannel !== 'function') return;
            if (!this._agentChatChangeChannel) {
                this._agentChatChangeChannel = new window.BroadcastChannel(
                    'chatraw-agent-chats-v1'
                );
                this._agentChatChangeChannel.addEventListener(
                    'message',
                    async event => {
                        if (event.data?.type !== 'agent-chats-changed') return;
                        await this.loadAgentChats();
                        if (
                            this.currentChatId
                            && !this.chats.some(
                                chat => chat.id === this.currentChatId
                            )
                        ) {
                            if (this.isGenerating) this.stopGeneration();
                            this.currentChatId = null;
                            this.messages = [];
                        }
                    }
                );
            }
            if (!this._settingsChangeChannel) {
                this._settingsChangeChannel = new window.BroadcastChannel(
                    'chatraw-settings-v1'
                );
                this._settingsChangeChannel.addEventListener(
                    'message',
                    async event => {
                        if (event.data?.type !== 'settings-changed') return;
                        await this.loadSettings();
                        this.applyTheme();
                    }
                );
            }
        },

        announceAgentChatChange(action, chatId) {
            this._agentChatChangeChannel?.postMessage({
                type: 'agent-chats-changed',
                action,
                chat_id: chatId
            });
        },

        announceSettingsChange() {
            this._settingsChangeChannel?.postMessage({
                type: 'settings-changed'
            });
        },

        isAdmin() {
            return this.me?.role === 'admin';
        },

        async loadMe() {
            const response = await fetch('/api/me');
            if (!response.ok) {
                location.replace('/login');
                throw new Error(this.t('authenticationRequired'));
            }
            this.me = await response.json();
            if (!this.isAdmin()) this.settingsTab = 'account';
        },

        async logout() {
            await fetch('/api/auth/logout', { method: 'POST' });
            location.replace('/login');
        },

        async loadFeatureCatalog() {
            this.featureCatalogLoading = true;
            try {
                const response = await fetch('/api/module-feature-catalog');
                if (!response.ok) throw new Error('Feature catalog unavailable');
                const catalog = await response.json();
                this.featureCatalog = {
                    categories: Array.isArray(catalog.categories)
                        ? catalog.categories
                        : [],
                    cards: Array.isArray(catalog.cards) ? catalog.cards : []
                };
                this.recomputeFeatureCatalogRuntime();
                if (
                    !this.featureCatalog.categories.some(
                        category => category.id === this.activeFeatureCategory
                    )
                ) {
                    this.activeFeatureCategory = this.featureCatalog.categories[0]?.id || '';
                }
            } catch (error) {
                console.error('Failed to load feature catalog:', error);
                this.featureCatalog = { categories: [], cards: [] };
            } finally {
                this.featureCatalogLoading = false;
            }
        },

        get activeFeatureCards() {
            return this.featureCatalog.cards
                .filter(card => card.category_id === this.activeFeatureCategory)
                .sort((left, right) => left.order - right.order);
        },

        featureCatalogCardForPanel(pluginId, panelId) {
            return this.featureCatalog.cards.find(card => (
                card.plugin_id === pluginId
                && card.panel_id === panelId
            )) || null;
        },

        pluginWorkspacePanelIcon(pluginId, panelId, fallback = '') {
            return this.featureCatalogCardForPanel(pluginId, panelId)?.icon
                || fallback;
        },

        featureStateLabel(state) {
            return this.t({
                loading: 'featureLoading',
                module_unavailable: 'moduleUnavailable',
                plugin_missing: 'pluginMissing',
                plugin_disabled: 'pluginDisabledState',
                plugin_version_mismatch: 'pluginVersionMismatch',
                panel_not_registered: 'panelNotRegistered',
                main_placement_required: 'mainPlacementRequired',
                available: 'featureAvailable'
            }[state] || 'featureUnavailable');
        },

        recomputeFeatureCatalogRuntime() {
            this.featureCatalog = {
                ...this.featureCatalog,
                cards: this.featureCatalog.cards.map(card => {
                    if (!card.service_ready) {
                        return {
                            ...card,
                            runtime_ready: false,
                            available: false
                        };
                    }
                    const definition = this.pluginWorkspaceDefinitions[
                        this.pluginWorkspaceKey(card.plugin_id, card.panel_id)
                    ];
                    if (!definition) {
                        return {
                            ...card,
                            runtime_ready: false,
                            available: false,
                            state: 'panel_not_registered'
                        };
                    }
                    if (!definition.placements.includes('main')) {
                        return {
                            ...card,
                            runtime_ready: false,
                            available: false,
                            state: 'main_placement_required'
                        };
                    }
                    return {
                        ...card,
                        runtime_ready: true,
                        available: true,
                        state: 'available'
                    };
                })
            };
        },

        async openFeatureCard(card, trigger = null) {
            if (!card?.available) return;
            const key = this.pluginWorkspaceKey(card.plugin_id, card.panel_id);
            if (!this.pluginWorkspaceDefinitions[key]) {
                await this.syncPluginRuntimes();
            }
            if (!this.pluginWorkspaceDefinitions[key]) {
                this.recomputeFeatureCatalogRuntime();
                this.showToast(this.t('featurePanelNotReady'), 'error');
                return;
            }
            const definition = this.pluginWorkspaceDefinitions[key];
            if (!definition.placements.includes('main')) {
                this.recomputeFeatureCatalogRuntime();
                this.showToast(this.t('featurePanelNotReady'), 'error');
                return;
            }
            const placement = 'main';
            this.showSettings = false;
            if (this.isGenerating) this.stopGeneration();
            this.agentOpen = false;
            this.agentExpanded = false;
            this.agentHistoryOpen = false;
            const previousActivation = this._pluginWorkspaceActivation;
            this._pluginWorkspaceActivation = (
                navigator.userActivation?.isActive === true
                && trigger instanceof HTMLElement
                && trigger.isConnected
            ) ? { pluginId: card.plugin_id, trigger } : null;
            try {
                this.openPluginWorkspacePanel(
                    card.panel_id,
                    { placement },
                    card.plugin_id
                );
            } finally {
                this._pluginWorkspaceActivation = previousActivation;
            }
        },

        returnHome() {
            this.showSettings = false;
            if (this.pluginWorkspace.show) this.closeActivePluginWorkspace();
        },

        toggleAgent() {
            if (!this.agentOpen) {
                this.showSettings = false;
                this.showPlugins = false;
            }
            this.agentOpen = !this.agentOpen;
            if (!this.agentOpen) {
                this.agentHistoryOpen = false;
                this.agentExpanded = false;
            }
            if (this.agentOpen && !this.currentChatId && this.chats.length) {
                this.selectChat(this.chats[0].id);
            }
        },

        toggleAgentExpanded() {
            if (!this.agentOpen) return;
            this.agentExpanded = !this.agentExpanded;
            if (this.agentExpanded) this.agentHistoryOpen = false;
        },

        async loadAdminUsers() {
            if (!this.isAdmin()) return;
            this.adminUsersLoading = true;
            this.adminUsersError = null;
            try {
                const response = await fetch('/api/admin/users');
                let data = {};
                try {
                    data = await response.json();
                } catch (_error) {
                    data = {};
                }
                if (!response.ok) throw data;
                this.adminUsers = Array.isArray(data.users) ? data.users : [];
            } catch (error) {
                this.adminUsers = [];
                this.adminUsersError = this.localizeError(error, 'usersLoadFailed');
            } finally {
                this.adminUsersLoading = false;
            }
        },

        setAdminUserBusy(userId, busy) {
            const next = { ...this.adminUserBusy };
            if (busy) next[userId] = true;
            else delete next[userId];
            this.adminUserBusy = next;
        },

        isAdminUserBusy(userId) {
            return Boolean(this.adminUserBusy[userId]);
        },

        formatUserDate(value) {
            if (!value) return '—';
            const parsed = new Date(value);
            if (Number.isNaN(parsed.getTime())) return value;
            return new Intl.DateTimeFormat(this.lang === 'zh' ? 'zh-CN' : 'en', {
                dateStyle: 'medium',
                timeStyle: 'short'
            }).format(parsed);
        },

        managedUserSnapshot(user) {
            return {
                id: String(user.id),
                username: String(user.username),
                role: user.role,
                enabled: Boolean(user.enabled)
            };
        },

        async createManagedUser() {
            if (this.adminCreateBusy) return;
            if (this.newUser.password.length < 12) {
                this.showToast(this.t('passwordMinimum'), 'error');
                return;
            }
            if (this.newUser.password !== this.newUser.confirmPassword) {
                this.showToast(this.t('passwordsDoNotMatch'), 'error');
                return;
            }
            if (
                this.newUser.role === 'admin'
                && !window.confirm(this.t('administratorAccessWarning'))
            ) {
                return;
            }
            const payload = {
                username: this.newUser.username,
                password: this.newUser.password,
                role: this.newUser.role
            };
            this.adminCreateBusy = true;
            try {
                const response = await fetch('/api/admin/users', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(payload)
                });
                let result = {};
                try {
                    result = await response.json();
                } catch (_error) {
                    result = {};
                }
                if (!response.ok) {
                    this.showToast(this.localizeError(result, 'unableCreateUser'), 'error');
                    return;
                }
                this.newUser = {
                    username: '',
                    password: '',
                    confirmPassword: '',
                    role: 'member'
                };
                await this.loadAdminUsers();
                this.showToast(this.t('userCreated'), 'success');
            } catch (error) {
                this.showToast(this.localizeError(error, 'unableCreateUser'), 'error');
            } finally {
                this.adminCreateBusy = false;
            }
        },

        async setManagedUserEnabled(user, enabled) {
            const target = this.managedUserSnapshot(user);
            if (target.id === this.me?.id || this.isAdminUserBusy(target.id)) return;
            if (
                !enabled
                && !window.confirm(this.t('confirmDisableUser', {
                    username: target.username
                }))
            ) {
                return;
            }
            const action = enabled ? 'enable' : 'disable';
            this.setAdminUserBusy(target.id, true);
            try {
                const response = await fetch(
                    `/api/admin/users/${encodeURIComponent(target.id)}/${action}`,
                    { method: 'POST' }
                );
                let result = {};
                try {
                    result = await response.json();
                } catch (_error) {
                    result = {};
                }
                if (!response.ok) {
                    this.showToast(this.localizeError(result, 'unableUpdateUser'), 'error');
                    return;
                }
                await this.loadAdminUsers();
                this.showToast(this.t('userUpdated'), 'success');
            } catch (error) {
                this.showToast(this.localizeError(error, 'unableUpdateUser'), 'error');
            } finally {
                this.setAdminUserBusy(target.id, false);
            }
        },

        async setManagedUserRole(user, role) {
            const target = this.managedUserSnapshot(user);
            if (
                target.id === this.me?.id
                || target.role === role
                || this.isAdminUserBusy(target.id)
            ) {
                return;
            }
            const confirmKey = role === 'admin'
                ? 'confirmPromoteUser'
                : 'confirmDemoteUser';
            if (!window.confirm(this.t(confirmKey, { username: target.username }))) {
                return;
            }
            this.setAdminUserBusy(target.id, true);
            try {
                const response = await fetch(
                    `/api/admin/users/${encodeURIComponent(target.id)}/role`,
                    {
                        method: 'PUT',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ role })
                    }
                );
                let result = {};
                try {
                    result = await response.json();
                } catch (_error) {
                    result = {};
                }
                if (!response.ok) {
                    this.showToast(this.localizeError(result, 'unableUpdateUser'), 'error');
                    return;
                }
                await this.loadAdminUsers();
                this.showToast(this.t('userRoleUpdated'), 'success');
            } catch (error) {
                this.showToast(this.localizeError(error, 'unableUpdateUser'), 'error');
            } finally {
                this.setAdminUserBusy(target.id, false);
            }
        },

        resetManagedUserPassword(user) {
            const target = this.managedUserSnapshot(user);
            if (target.id === this.me?.id || this.isAdminUserBusy(target.id)) return;
            this.resetUserPasswordDialog = {
                show: true,
                user: target,
                newPassword: '',
                confirmPassword: ''
            };
        },

        closeManagedUserPasswordDialog() {
            this.resetUserPasswordDialog = {
                show: false,
                user: null,
                newPassword: '',
                confirmPassword: ''
            };
        },

        async submitManagedUserPasswordReset() {
            const dialog = this.resetUserPasswordDialog;
            const target = dialog.user ? { ...dialog.user } : null;
            if (!target || this.isAdminUserBusy(target.id)) return;
            if (dialog.newPassword.length < 12) {
                this.showToast(this.t('passwordMinimum'), 'error');
                return;
            }
            if (dialog.newPassword !== dialog.confirmPassword) {
                this.showToast(this.t('passwordsDoNotMatch'), 'error');
                return;
            }
            this.setAdminUserBusy(target.id, true);
            try {
                const response = await fetch(
                    `/api/admin/users/${encodeURIComponent(target.id)}/reset-password`,
                    {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ new_password: dialog.newPassword })
                    }
                );
                let result = {};
                try {
                    result = await response.json();
                } catch (_error) {
                    result = {};
                }
                if (!response.ok) {
                    this.showToast(this.localizeError(result, 'unableResetPassword'), 'error');
                    return;
                }
                this.closeManagedUserPasswordDialog();
                await this.loadAdminUsers();
                this.showToast(this.t('passwordReset'), 'success');
            } catch (error) {
                this.showToast(this.localizeError(error, 'unableResetPassword'), 'error');
            } finally {
                this.setAdminUserBusy(target.id, false);
            }
        },

        async changeMyPassword() {
            const response = await fetch('/api/me/password', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(this.passwordForm)
            });
            const result = await response.json();
            if (!response.ok) {
                this.showToast(this.localizeError(result, 'unableChangePassword'), 'error');
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
                const error = new Error(this.localizeError(result, 'moduleOperationFailed'));
                error.code = result.code || result.error?.code || result.detail?.code || '';
                throw error;
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

        createModuleTaskView(task, presentation = 'task_center') {
            const terminal = MODULE_TERMINAL_STATES.has(task?.state);
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
                    ? (task.outcome_code || 'task_failed')
                    : null,
                inline: false,
                activities: {},
                activityOrder: [],
                activitiesLoaded: false,
                currentRunId: null,
                timelineExpanded: !terminal,
                timelineTouched: false,
                lastAppliedEventId: 0,
                presentation,
                attentionPending: false
            };
        },

        upsertModuleTask(
            task,
            { select = false, presentation = null } = {}
        ) {
            const taskId = task?.task_id;
            if (!taskId) return null;
            let view = this.moduleTasks[taskId];
            if (!view) {
                view = this.createModuleTaskView(
                    task,
                    presentation || 'task_center'
                );
                this.moduleTasks[taskId] = view;
                this.moduleTaskOrder = [
                    taskId,
                    ...this.moduleTaskOrder.filter(item => item !== taskId)
                ].slice(0, 20);
            } else {
                view.task = task;
                if (presentation) view.presentation = presentation;
                view.artifacts = Array.isArray(task.artifacts)
                    ? task.artifacts
                    : view.artifacts;
                if (MODULE_TERMINAL_STATES.has(task.state)) {
                    view.progress = 1;
                    view.approval = null;
                    view.error = task.state === 'failed'
                        ? (task.outcome_code || 'task_failed')
                        : null;
                    if (!view.timelineTouched) {
                        view.timelineExpanded = false;
                    }
                }
            }
            if (select) this.selectModuleTask(taskId);
            return view;
        },

        moduleTaskActivityList(view) {
            if (!view) return [];
            return view.activityOrder
                .map(key => view.activities[key])
                .filter(Boolean);
        },

        moduleTaskActivityKey(activity) {
            return `${activity.run_id}:${activity.activity_id}`;
        },

        upsertModuleTaskActivity(view, activity) {
            if (!view || !activity) return;
            if (
                view.currentRunId
                && view.currentRunId !== activity.run_id
            ) {
                for (const current of Object.values(view.activities)) {
                    if (
                        current.run_id === view.currentRunId
                        && current.state === 'started'
                    ) {
                        current.interrupted = true;
                    }
                }
            }
            view.currentRunId = activity.run_id;
            const key = this.moduleTaskActivityKey(activity);
            if (!view.activities[key]) {
                if (view.activityOrder.length >= MODULE_ACTIVITY_LIMIT) {
                    const removed = view.activityOrder.shift();
                    if (removed) delete view.activities[removed];
                }
                view.activityOrder.push(key);
            }
            view.activities[key] = {
                ...activity,
                interrupted: false
            };
            view.activitiesLoaded = true;
        },

        moduleTaskActivityIcon(activity) {
            if (activity?.kind === 'plan') return 'ri-list-check-3';
            if (activity?.kind === 'tool') return 'ri-tools-line';
            if (activity?.detail?.phase === 'preparing') {
                return 'ri-loader-4-line';
            }
            if (activity?.detail?.phase === 'finalizing') {
                return 'ri-quill-pen-line';
            }
            return 'ri-play-circle-line';
        },

        moduleTaskActivityState(activity) {
            if (activity?.interrupted) return this.t('activityInterrupted');
            const key = {
                started: 'activityRunning',
                updated: 'activityUpdated',
                succeeded: 'stateSucceeded',
                failed: 'stateFailed',
                cancelled: 'stateCancelled'
            }[activity?.state];
            return this.t(key || 'stateUnknown');
        },

        formatModuleTaskDuration(durationMs) {
            if (!Number.isFinite(durationMs) || durationMs < 0) return '';
            if (durationMs < 1000) return `${Math.round(durationMs)} ms`;
            return `${(durationMs / 1000).toFixed(1)} s`;
        },

        messageContent(message) {
            return typeof message?.content === 'string'
                ? message.content
                : '';
        },

        syncConversationTaskMessage(view) {
            const taskId = view?.task?.task_id;
            if (!taskId || view.presentation !== 'conversation') return;
            const messageId = `module-task:${taskId}`;
            const messageIndex = this.messages.findIndex(
                message => message.id === messageId
            );
            if (messageIndex < 0) return;
            this.messages[messageIndex] = {
                ...this.messages[messageIndex],
                content: view.output
            };
        },

        async toggleModuleTaskTimeline(view) {
            if (!view) return;
            view.timelineExpanded = !view.timelineExpanded;
            view.timelineTouched = true;
            if (
                view.timelineExpanded
                && MODULE_TERMINAL_STATES.has(view.task?.state)
                && !view.activitiesLoaded
            ) {
                window.ChatRaw.modules.subscribe(view.task.task_id, {
                    onClose: () => {
                        view.activitiesLoaded = true;
                    }
                });
            }
        },

        mergeConversationTaskMessages(messages, tasks) {
            const baseMessages = Array.isArray(messages)
                ? messages.map(message => ({ ...message }))
                : [];
            const messageIds = new Set(
                baseMessages
                    .map(message => message.id)
                    .filter(Boolean)
            );
            const byAssistant = new Map();
            const byUser = new Map();
            for (const task of tasks || []) {
                if (!task?.task_id || !task.user_message_id) continue;
                const view = this.upsertModuleTask(task, {
                    presentation: 'conversation'
                });
                view.inline = true;
                if (task.assistant_message_id) {
                    byAssistant.set(task.assistant_message_id, view);
                }
                if (!byUser.has(task.user_message_id)) {
                    byUser.set(task.user_message_id, []);
                }
                byUser.get(task.user_message_id).push(view);
            }

            const merged = [];
            for (const message of baseMessages) {
                const assistantView = byAssistant.get(message.id);
                if (assistantView) message.moduleTask = assistantView;
                merged.push(message);
                if (message.role !== 'user') continue;
                const views = byUser.get(message.id) || [];
                for (const view of views.reverse()) {
                    const assistantId = view.task.assistant_message_id;
                    if (assistantId && messageIds.has(assistantId)) continue;
                    merged.push({
                        id: `module-task:${view.task.task_id}`,
                        chat_id: view.task.chat_id,
                        role: 'assistant',
                        content: view.output,
                        created_at: view.task.created_at,
                        moduleTask: view
                    });
                }
            }
            return merged;
        },

        attachConversationTask(task, userMessage) {
            const view = this.upsertModuleTask(task, {
                presentation: 'conversation'
            });
            view.inline = true;
            if (
                task.chat_id !== this.currentChatId
                || !task.user_message_id
            ) {
                return view;
            }
            const persistentMessages = this.messages.filter(
                message => !String(message.id || '').startsWith(
                    'module-task:'
                )
            );
            if (
                !persistentMessages.some(
                    message => message.id === task.user_message_id
                )
            ) {
                persistentMessages.push({
                    id: task.user_message_id,
                    chat_id: task.chat_id,
                    role: 'user',
                    content: String(userMessage),
                    created_at: task.accepted_at || task.created_at
                });
            }
            this.messages = this.mergeConversationTaskMessages(
                persistentMessages,
                [task]
            );
            this.$nextTick(() => this.scrollToBottom());
            return view;
        },

        moduleTaskViews() {
            return this.moduleTaskOrder
                .map(taskId => this.moduleTasks[taskId])
                .filter(view => (
                    view
                    && view.presentation === 'task_center'
                    && (
                        !MODULE_TERMINAL_STATES.has(view.task?.state)
                        || view.attentionPending
                        || view.show
                    )
                ));
        },

        moduleTaskAttentionViews() {
            return this.moduleTaskViews().filter(view => (
                !MODULE_TERMINAL_STATES.has(view.task?.state)
                || view.attentionPending
            ));
        },

        selectModuleTask(taskId) {
            const view = this.moduleTasks[taskId];
            if (!view) return;
            this.moduleTaskUi.show = false;
            view.show = true;
            this.moduleTaskUi = view;
        },

        openModuleTaskCenter() {
            const attentionViews = this.moduleTaskAttentionViews();
            const currentTaskId = this.moduleTaskUi.task?.task_id;
            const first = attentionViews.some(
                view => view.task.task_id === currentTaskId
            )
                ? currentTaskId
                : attentionViews[0]?.task?.task_id;
            if (first) this.selectModuleTask(first);
        },

        closeModuleTask() {
            const view = this.moduleTaskUi;
            view.show = false;
            if (MODULE_TERMINAL_STATES.has(view.task?.state)) {
                view.attentionPending = false;
                this.forgetModuleTask(view.task.task_id);
            }
        },

        applyModuleTaskEvent(taskId, event) {
            const ui = this.moduleTasks[taskId];
            if (!ui) return;
            if (event.id <= ui.lastAppliedEventId) return;
            ui.lastAppliedEventId = event.id;
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
                        ui.error = event.data.outcome_code || 'task_failed';
                    }
                    ui.approval = null;
                    ui.activitiesLoaded = true;
                    if (!ui.timelineTouched) {
                        ui.timelineExpanded = false;
                    }
                    if (
                        ui.presentation === 'task_center'
                        && event.data.state !== 'cancelled'
                        && !ui.show
                    ) {
                        ui.attentionPending = true;
                    } else if (
                        ui.presentation !== 'task_center'
                        || event.data.state === 'cancelled'
                    ) {
                        this.forgetModuleTask(taskId);
                    }
                }
            } else if (event.event === 'task.progress') {
                ui.progress = event.data.progress;
                ui.progressMessage = this.t('taskInProgress');
            } else if (event.event === 'activity.updated') {
                this.upsertModuleTaskActivity(ui, event.data);
            } else if (event.event === 'output.delta') {
                ui.output += event.data.text;
                this.syncConversationTaskMessage(ui);
            } else if (event.event === 'output.snapshot') {
                ui.output = event.data.text;
                this.syncConversationTaskMessage(ui);
            } else if (event.event === 'approval.requested') {
                ui.approval = event.data;
            } else if (event.event === 'approval.resolved') {
                ui.approval = null;
            }
        },

        async resolveModuleTaskApproval(decision) {
            return this.resolveModuleTaskApprovalFor(
                this.moduleTaskUi,
                decision
            );
        },

        async resolveModuleTaskApprovalFor(view, decision) {
            const task = view?.task;
            const approval = view?.approval;
            if (!task || !approval) return;
            try {
                await window.ChatRaw.modules.respondApproval(
                    task.task_id,
                    approval.approval_id,
                    decision
                );
            } catch (error) {
                view.error = {
                    code: error?.code || 'invalid_request'
                };
            }
        },

        async cancelVisibleModuleTask() {
            const taskId = this.moduleTaskUi.task?.task_id;
            if (!taskId) return;
            try {
                const task = await window.ChatRaw.modules.cancelTask(taskId);
                this.upsertModuleTask(task);
            } catch (error) {
                this.moduleTaskUi.error = {
                    code: error?.code || 'invalid_request'
                };
            }
        },

        async downloadVisibleModuleArtifact(artifact) {
            return this.downloadModuleTaskArtifact(
                this.moduleTaskUi,
                artifact
            );
        },

        async downloadModuleTaskArtifact(view, artifact) {
            const taskId = view?.task?.task_id;
            if (!taskId) return;
            try {
                await window.ChatRaw.modules.downloadArtifact(
                    taskId,
                    artifact.artifact_ref
                );
            } catch (error) {
                view.error = {
                    code: error?.code || 'invalid_request'
                };
            }
        },

        async resumeModuleTasks() {
            if (!window.ChatRaw?.modules) return;
            for (const taskId of this.moduleTaskIds()) {
                try {
                    const task = await window.ChatRaw.modules.getTask(taskId);
                    if (MODULE_TERMINAL_STATES.has(task.state)) {
                        this.forgetModuleTask(taskId);
                        continue;
                    }
                    this.upsertModuleTask(task, {
                        presentation: 'task_center'
                    });
                    window.ChatRaw.modules.subscribe(taskId);
                } catch (error) {
                    if (error?.status === 404) this.forgetModuleTask(taskId);
                }
            }
        },

        residentText(value) {
            if (!value || typeof value !== 'object') return '';
            return value[this.lang] || value.en || value.zh || '';
        },

        residentEntries(placement) {
            return this.residentIntegrations
                .filter(integration => integration.feature?.visible === true)
                .flatMap(integration => (
                    (integration.entrypoints || [])
                        .filter(entrypoint => (
                            entrypoint.placement === placement
                            || (
                                placement === 'composer'
                                && entrypoint.placement === 'sidebar'
                            )
                        ))
                        .map(entrypoint => ({
                            ...entrypoint,
                            integration
                        }))
                ))
                .sort((left, right) => (
                    (left.order ?? 100) - (right.order ?? 100)
                ));
        },

        async refreshResidentIntegrationStatuses() {
            if (!window.ChatRaw?.modules) return;
            for (const integration of this.residentIntegrations) {
                try {
                    integration.feature = await window.ChatRaw.modules
                        .getFeatureStatus(integration.module_id);
                } catch (error) {
                    integration.feature = {
                        visible: false,
                        available: false,
                        state: 'hidden',
                        reason: {
                            code: error?.code || 'module_not_found',
                            message: 'This feature is currently unavailable.'
                        }
                    };
                }
            }
        },

        registerResidentIntegration(definition) {
            if (
                !this.residentRegistrationOpen
                || !definition
                || typeof definition.id !== 'string'
                || typeof definition.mount !== 'function'
                || Object.keys(definition).some(
                    key => !['id', 'mount'].includes(key)
                )
                || !this.residentBuiltIntegrationIds.includes(definition.id)
                || this.residentIntegrationDefinitions[definition.id]
            ) {
                throw new Error('Resident Integration registration rejected');
            }
            this.residentIntegrationDefinitions[definition.id] = Object.freeze({
                id: definition.id,
                mount: definition.mount
            });
        },

        async initResidentIntegrations() {
            const response = await fetch('/api/resident-integrations', {
                credentials: 'same-origin'
            });
            if (!response.ok) {
                throw new Error('Resident Integration catalog unavailable');
            }
            const payload = await response.json();
            if (
                typeof payload.bundle_version !== 'string'
                || !/^[0-9a-f]{64}$/.test(payload.bundle_version)
                || !Array.isArray(payload.built_integration_ids)
                || payload.built_integration_ids.some(
                    integrationId => (
                        typeof integrationId !== 'string'
                        || !integrationId
                    )
                )
                || new Set(payload.built_integration_ids).size
                    !== payload.built_integration_ids.length
            ) {
                throw new Error('Resident Integration catalog unavailable');
            }
            this.residentBuiltIntegrationIds = [
                ...payload.built_integration_ids
            ];
            this.residentIntegrations = Array.isArray(payload.integrations)
                ? payload.integrations.map(integration => ({
                    ...integration,
                    feature: {
                        visible: false,
                        available: false,
                        state: 'hidden',
                        reason: {
                            code: 'module_not_found',
                            message: 'This feature is currently unavailable.'
                        }
                    }
                }))
                : [];
            if (!this.residentIntegrations.length) return;

            const appInstance = this;
            window.ChatRawResident = Object.freeze({
                register(definition) {
                    appInstance.registerResidentIntegration(definition);
                }
            });
            this.residentRegistrationOpen = true;
            try {
                await this.loadCSS(
                    '/resident-integrations/resident-integrations.min.css?v='
                    + encodeURIComponent(payload.bundle_version)
                );
                await this.loadScript(
                    '/resident-integrations/resident-integrations.min.js?v='
                    + encodeURIComponent(payload.bundle_version)
                );
            } finally {
                this.residentRegistrationOpen = false;
            }
            for (const integrationId of this.residentBuiltIntegrationIds) {
                if (!this.residentIntegrationDefinitions[integrationId]) {
                    throw new Error(
                        `Resident Integration ${integrationId} did not register`
                    );
                }
            }
            await this.refreshResidentIntegrationStatuses();
            this._residentFocusHandler = () => {
                this.refreshResidentIntegrationStatuses().catch(error => {
                    console.warn('[Resident Integration refresh]', error);
                });
            };
            window.addEventListener('focus', this._residentFocusHandler);
        },

        async openResidentIntegration(integration) {
            await this.refreshResidentIntegrationStatuses();
            const current = this.residentIntegrations.find(
                item => item.id === integration.id
            );
            if (!current?.feature?.available) {
                this.showToast(
                    current?.feature?.reason?.message
                        || 'This feature is currently unavailable.',
                    'error'
                );
                return;
            }
            this.closeResidentWorkspace();
            this.residentWorkspace = {
                show: true,
                integrationId: current.id,
                title: this.residentText(current.name),
                error: null,
                cleanup: null
            };
            await new Promise(resolve => requestAnimationFrame(resolve));
            const container = document.getElementById(
                'resident-workspace-mount'
            );
            const definition = this.residentIntegrationDefinitions[current.id];
            if (!container || !definition) {
                this.residentWorkspace.error = (
                    'Resident Integration failed to mount'
                );
                return;
            }
            try {
                const cleanup = await definition.mount({
                    container,
                    moduleId: current.module_id,
                    modules: window.ChatRaw.modules,
                    t: value => this.residentText(value),
                    showToast: (message, type = '') => (
                        this.showToast(message, type)
                    ),
                    getCurrentChatId: () => this.currentChatId
                });
                if (typeof cleanup === 'function') {
                    this.residentWorkspace.cleanup = cleanup;
                }
            } catch (error) {
                container.replaceChildren();
                this.residentWorkspace.error = (
                    error?.message || 'Resident Integration failed to mount'
                );
            }
        },

        closeResidentWorkspace() {
            try {
                this.residentWorkspace.cleanup?.();
            } catch (error) {
                console.warn('[Resident Integration cleanup]', error);
            }
            const container = document.getElementById(
                'resident-workspace-mount'
            );
            container?.replaceChildren();
            this.residentWorkspace = {
                show: false,
                integrationId: null,
                title: '',
                error: null,
                cleanup: null
            };
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
                this.showToast(this.localizeError(error, 'moduleOperationFailed'), 'error');
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
                await this.refreshResidentIntegrationStatuses();
                this.showToast(this.t('modulePaired'), 'success');
            } catch (error) {
                this.showToast(this.localizeError(error, 'moduleOperationFailed'), 'error');
            } finally {
                this.moduleBusy = null;
            }
        },

        async approveModule(module) {
            if (!this.isAdmin() || this.moduleBusy) return;
            if (!window.confirm(this.t('approveModuleConfirm', { moduleId: module.module_id }))) return;
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
                await this.refreshResidentIntegrationStatuses();
                this.showToast(this.t('moduleApproved'), 'success');
            } catch (error) {
                this.showToast(this.localizeError(error, 'moduleOperationFailed'), 'error');
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
                await this.refreshResidentIntegrationStatuses();
                this.showToast(this.t('moduleActionCompleted', {
                    action: this.actionLabel(action)
                }), 'success');
            } catch (error) {
                this.showToast(this.localizeError(error, 'moduleOperationFailed'), 'error');
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
                this.showToast(this.localizeError(error, 'moduleOperationFailed'), 'error');
            } finally {
                this.moduleBusy = null;
            }
        },

        async saveModuleConfig() {
            if (!this.isAdmin() || !this.moduleConfig || this.moduleBusy) return;
            this.moduleBusy = this.moduleConfig.moduleId;
            const moduleId = this.moduleConfig.moduleId;
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
                if (config.configured) {
                    try {
                        await this.recheckModuleAfterConfig(moduleId);
                    } catch (error) {
                        console.warn(
                            '[Module configuration recheck]',
                            error?.code || error?.name || 'failed'
                        );
                    }
                }
                await this.loadModules();
                await this.refreshResidentIntegrationStatuses();
                this.showToast(this.t('configurationSavedRevision', {
                    revision: config.revision
                }), 'success');
            } catch (error) {
                this.showToast(this.localizeError(error, 'moduleOperationFailed'), 'error');
            } finally {
                this.moduleBusy = null;
            }
        },

        async recheckModuleAfterConfig(moduleId) {
            const maxAttempts = 6;
            let module = null;
            for (let attempt = 0; attempt < maxAttempts; attempt += 1) {
                if (attempt > 0) {
                    await new Promise(resolve => setTimeout(resolve, 750));
                }
                module = await this.moduleApi(
                    `/api/admin/modules/${encodeURIComponent(moduleId)}/check`,
                    { method: 'POST' }
                );
                if (module.ready_status === 'ready') return module;
                if (
                    module.health_status === 'incompatible'
                    || module.config_status === 'missing'
                ) {
                    return module;
                }
            }
            return module;
        },

        async disconnectModule(module) {
            if (!this.isAdmin() || this.moduleBusy) return;
            const confirmation = window.prompt(this.t('disconnectModulePrompt', {
                moduleId: module.module_id
            }));
            if (confirmation !== module.module_id) return;
            this.moduleBusy = module.id;
            try {
                await this.moduleApi(`/api/admin/modules/${encodeURIComponent(module.id)}/disconnect`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ confirmation })
                });
                await this.loadModules();
                await this.refreshResidentIntegrationStatuses();
                this.showToast(this.t('moduleDisconnected'), 'success');
            } catch (error) {
                this.showToast(this.localizeError(error, 'moduleOperationFailed'), 'error');
            } finally {
                this.moduleBusy = null;
            }
        },

        async purgeModuleData(module) {
            if (!this.isAdmin() || !module.supports_data_purge || this.moduleBusy) return;
            const expected = `PURGE ${module.module_id}`;
            const confirmation = window.prompt(this.t('purgeModulePrompt', {
                confirmation: expected
            }));
            if (confirmation !== expected) return;
            this.moduleBusy = module.id;
            try {
                await this.moduleApi(`/api/admin/modules/${encodeURIComponent(module.id)}/purge-data`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ confirmation })
                });
                await this.loadModules();
                this.showToast(this.t('moduleDataPurged'), 'success');
            } catch (error) {
                this.showToast(this.localizeError(error, 'moduleOperationFailed'), 'error');
            } finally {
                this.moduleBusy = null;
            }
        },
        
        openSettingsPanel() {
            this.showPlugins = false;
            this.settingsTab = this.isAdmin() ? 'models' : 'account';
            this.showSettings = true;
            if (this.isGenerating) this.stopGeneration();
            this.agentOpen = false;
            this.agentExpanded = false;
            this.agentHistoryOpen = false;
            if (this.pluginWorkspace.show) this.closeActivePluginWorkspace();
            if (this.isAdmin()) {
                this.loadAdminUsers();
                this.loadModules();
            }
        },
        
        async openPluginsPanel() {
            if (!this.isAdmin()) return;
            this.showSettings = false;
            this.showPlugins = true;
            await this.loadInstalledPlugins();
            this.loadPluginMarket();
        },
        
        // Apply theme
        applyTheme() {
            this.settings.ui_settings.theme_mode = 'light';
            document.documentElement.setAttribute('data-theme', 'light');
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
                        this.settings.ui_settings.theme_mode = 'light';
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
                    this.settings.ui_settings.logo_data = data.logo_data || '';
                    if (typeof data.logo_text === 'string') {
                        this.settings.ui_settings.logo_text = data.logo_text;
                    }
                    this.updateFavicon(this.settings.ui_settings.logo_data);
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
            return this.loadAgentChats();
        },

        async loadAgentChats() {
            try {
                const res = await fetch('/api/agent/chats');
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
                const res = await fetch('/api/agent/chats', { method: 'POST' });
                if (res.ok) {
                    const chat = await res.json();
                    this.chats.unshift(chat);
                    await this.selectChat(chat.id);
                    this.agentHistoryOpen = false;
                    this.announceAgentChatChange('created', chat.id);
                }
            } catch (e) {
                this.showToast(this.t('createChatFailed'), 'error');
            }
        },

        async ensureCurrentChat(signal) {
            if (this.currentChatId) {
                return this.currentChatId;
            }
            const res = await fetch('/api/agent/chats', {
                method: 'POST',
                signal
            });
            if (!res.ok) {
                throw new Error(this.t('createChatFailed'));
            }
            const chat = await res.json();
            if (!chat || typeof chat.id !== 'string' || !chat.id) {
                throw new Error(this.t('createChatFailed'));
            }
            this.chats.unshift(chat);
            this.currentChatId = chat.id;
            return chat.id;
        },
        
        // Select chat
        async selectChat(chatId) {
            if (this.currentChatId === chatId) {
                this.agentHistoryOpen = false;
                return;
            }
            if (this.isGenerating) {
                this.stopGeneration();
            }
            this.currentChatId = chatId;
            this.messages = [];
            await this.loadMessages(chatId);
            this.agentHistoryOpen = false;
        },
        
        // Load messages
        async loadMessages(chatId) {
            try {
                const res = await fetch(`/api/agent/chats/${chatId}/messages`);
                if (!res.ok) {
                    if (res.status === 404 && this.currentChatId === chatId) {
                        this.currentChatId = null;
                        this.messages = [];
                        await this.loadAgentChats();
                    }
                    throw new Error(`Agent history request failed (${res.status})`);
                }
                if (this.currentChatId === chatId) {
                    const messages = await res.json() || [];
                    let tasks = [];
                    if (window.ChatRaw?.modules) {
                        try {
                            tasks = await window.ChatRaw.modules.listTasks({
                                chat_id: chatId,
                                limit: 100
                            });
                        } catch (error) {
                            console.error(
                                'Failed to load conversation tasks:',
                                error
                            );
                        }
                    }
                    this.messages = this.mergeConversationTaskMessages(
                        messages,
                        tasks
                    );
                    for (const task of tasks) {
                        if (
                            !MODULE_TERMINAL_STATES.has(task.state)
                            && !this.moduleTaskSubscriptions[task.task_id]
                        ) {
                            window.ChatRaw.modules.subscribe(task.task_id);
                        }
                    }
                    this.$nextTick(() => this.scrollToBottom());
                }
            } catch (e) {
                console.error('Failed to load messages:', e);
                if (this.currentChatId === chatId) {
                    this.messages = [];
                }
            }
        },
        
        // Delete chat
        async deleteChat(chatId) {
            if (!confirm(this.t('deleteSharedChat'))) return;
            try {
                if (this.currentChatId === chatId && this.isGenerating) {
                    this.stopGeneration();
                }
                const response = await fetch(`/api/agent/chats/${chatId}`, { method: 'DELETE' });
                if (!response.ok) {
                    const result = await response.json();
                    throw new Error(result.detail || this.t('deleteFailed'));
                }
                this.chats = this.chats.filter(c => c.id !== chatId);
                if (this.currentChatId === chatId) {
                    this.currentChatId = null;
                    this.messages = [];
                }
                this.announceAgentChatChange('deleted', chatId);
            } catch (e) {
                this.showToast(this.t('deleteFailed'), 'error');
            }
        },

        async renameChat(chat) {
            const title = window.prompt(this.t('renameSharedChat'), chat.title);
            if (!title || title.trim() === chat.title) return;
            const response = await fetch(`/api/agent/chats/${encodeURIComponent(chat.id)}`, {
                method: 'PATCH',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ title: title.trim() })
            });
            const result = await response.json();
            if (!response.ok) {
                this.showToast(this.localizeError(result, 'renameFailed'), 'error');
                return;
            }
            chat.title = result.title;
            this.announceAgentChatChange('renamed', chat.id);
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
                    const response = await fetch(`/api/agent/chats/${chat.id}`, { method: 'DELETE' });
                    if (!response.ok) throw new Error(this.t('deleteFailed'));
                }
                this.chats = [];
                this.currentChatId = null;
                this.messages = [];
                this.announceAgentChatChange('cleared', '');
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

                await this.ensureCurrentChat(sendController.signal);
                if (sendController.signal.aborted) return;

                this.inputMessage = '';
                this.closeCompletionMenu();
                this.$nextTick(() => this.autoResize(this.$refs.inputBox));

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
                    image_base64: this.uploadedImageBase64,
                    web_content: combinedContent,
                    web_url: contentSource
                };
                
                // Agent plugins may enrich only non-identity context. The Host
                // rewrites conversation and message identity after every hook.
                const beforeSendResult = await this.callHook(
                    'before_send',
                    { ...body }
                );
                if (sendController.signal.aborted) return;
                if (beforeSendResult?.success && beforeSendResult.body) {
                    const proposed = beforeSendResult.body;
                    for (const key of ['use_rag']) {
                        if (typeof proposed[key] === 'boolean') {
                            body[key] = proposed[key];
                        }
                    }
                    for (const key of ['web_content', 'web_url']) {
                        if (typeof proposed[key] === 'string') {
                            body[key] = proposed[key];
                        }
                    }
                }
                body.chat_id = this.currentChatId;
                body.message = message;
                if (activeSkillNames.length > 0) {
                    body.active_skills = activeSkillNames;
                } else {
                    delete body.active_skills;
                }

                if (sendController.signal.aborted) return;
                
                this.removeUploadedImage();
                this.removeParsedUrl();
                this.removeAttachedDocument();
                
                if (this.settings.chat_settings.stream) {
                    await this.handleStreamResponse(body, sendController.signal);
                } else {
                    await this.handleNormalResponse(body, sendController.signal);
                }
                await this.loadChats();
                
            } catch (e) {
                if (e.name === 'AbortError') {
                    // User cancelled, do nothing
                } else {
                    console.error('Failed to send message:', e);
                    if (this.currentChatId) {
                        try {
                            await this.loadMessages(this.currentChatId);
                        } catch (reloadError) {
                            console.error(
                                'Failed to recover persisted messages:',
                                reloadError
                            );
                        }
                    }
                    this.showToast(this.t('sendFailed'), 'error');
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
                hermesRun.approvalError = this.t('hermesApprovalError');
                this.commitHermesRunMessage(targetMessage, targetIndex);
            }
        },
        
        // Handle stream response (NDJSON format) - TRUE STREAMING
        async handleStreamResponse(body, signal = this.abortController?.signal) {
            const res = await fetch(AGENT_CHAT_ENDPOINT, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(body),
                signal
            });
            
            if (!res.ok) {
                const errText = await res.text();
                throw new Error(this.t('requestFailed'));
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
        async handleNormalResponse(body, signal = this.abortController?.signal) {
            const res = await fetch(AGENT_CHAT_ENDPOINT, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(body),
                signal
            });
            
            const data = await res.json();
            
            if (!res.ok) {
                throw new Error(this.t('requestFailed'));
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
                this.showToast(this.t('uploadFailed'), 'error');
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

        removeCustomLogo() {
            this.settings.ui_settings.logo_data = '';
            this.updateFavicon('');
        },

        handleLogoImageError(event) {
            const image = event?.currentTarget;
            if (!image) return;
            const source = image.getAttribute('src') || '';
            if (!source.endsWith('/brand-mark.svg') && source !== 'brand-mark.svg') {
                image.src = '/brand-mark.svg';
            }
        },
        
        // Update favicon
        updateFavicon(dataUrl) {
            const favicon = document.getElementById('favicon');
            if (dataUrl) {
                favicon.href = dataUrl;
            } else {
                favicon.href = '/brand-mark.svg';
            }
            this.updateDocumentTitle();
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
                                this.showToast(this.t('uploadFailed'), 'error');
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
                        this.showToast(this.t('uploadFailed'), 'error');
                    }
                }
            } catch (e) {
                console.error('Document upload error:', e);
                this.showToast(this.t('uploadFailed'), 'error');
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
                    this.showToast(this.t('parseFailed'), 'error');
                }
            } catch (e) {
                this.showToast(this.t('parseFailed'), 'error');
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
                this.settings.ui_settings.theme_mode = 'light';
                const settingsResponse = await fetch('/api/settings', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(this.settings)
                });
                if (!settingsResponse.ok) {
                    throw new Error(this.t('saveFailed'));
                }
                
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
                this.announceSettingsChange();
                this.showSettings = false;
                this.showToast(this.t('settingsSaved'), 'success');
                
                await this.loadModels();
                
            } catch (e) {
                await this.loadSettings();
                this.applyTheme();
                this.showToast(this.t('saveFailed'), 'error');
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
            return window.ChatRawContentSecurity.renderMarkdown(
                content,
                this.lang
            );
        },

        horizontalWheelDelta(event) {
            if (
                event.defaultPrevented
                || !event.cancelable
                || event.ctrlKey
            ) {
                return 0;
            }
            return Math.abs(event.deltaX) > Math.abs(event.deltaY)
                ? event.deltaX
                : event.shiftKey ? event.deltaY : 0;
        },

        findHorizontalWheelScroller(target) {
            let candidate = target instanceof Element ? target : null;
            while (candidate && candidate !== document.body) {
                const overflowX = getComputedStyle(candidate).overflowX;
                if (
                    candidate.scrollWidth > candidate.clientWidth
                    && (overflowX === 'auto' || overflowX === 'scroll')
                ) {
                    return candidate;
                }
                candidate = candidate.parentElement;
            }
            return null;
        },

        consumeHorizontalWheel(event, scroller = null) {
            const delta = this.horizontalWheelDelta(event);
            if (!delta) return false;
            event.preventDefault();
            event.stopPropagation();
            if (!scroller) return true;
            const scale = event.deltaMode === 1
                ? 16
                : event.deltaMode === 2 ? scroller.clientWidth : 1;
            const maxScrollLeft = scroller.scrollWidth - scroller.clientWidth;
            scroller.scrollLeft = Math.max(
                0,
                Math.min(maxScrollLeft, scroller.scrollLeft + delta * scale)
            );
            return true;
        },

        handleMarkdownTableWheel(event) {
            const scroller = event.target instanceof Element
                ? event.target.closest('.markdown-table-scroll')
                : null;
            if (
                !scroller
                || scroller.scrollWidth <= scroller.clientWidth
            ) {
                return false;
            }
            return this.consumeHorizontalWheel(event, scroller);
        },

        handleAppWheel(event) {
            if (event.defaultPrevented) return true;
            if (this.handleMarkdownTableWheel(event)) return true;
            const delta = this.horizontalWheelDelta(event);
            if (!delta) return false;
            return this.consumeHorizontalWheel(
                event,
                this.findHorizontalWheelScroller(event.target)
            );
        },

        installRootWheelGuard() {
            if (this._rootWheelHandler) return false;
            this._rootWheelHandler = event => this.handleAppWheel(event);
            document.addEventListener(
                'wheel',
                this._rootWheelHandler,
                { passive: false }
            );
            return true;
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
        getSortedPluginButtons(placement = 'toolbar') {
            return [...this.pluginToolbarButtons]
                .filter(btn => {
                    // Only show buttons from enabled plugins
                    const plugin = this.installedPlugins?.find(p => p.id === btn.pluginId);
                    // Hermes is the fixed runtime for the Agent surface. It is
                    // not a user-selectable composer mode anymore, so its
                    // legacy toolbar toggle must stay out of every placement.
                    return plugin?.enabled !== false
                        && btn.pluginId !== 'hermes'
                        && btn.placement === placement;
                })
                .sort((a, b) => (a.order || 100) - (b.order || 100));
        },
        
        // Computed: Visible plugin buttons (max 5)
        get visiblePluginButtons() {
            return this.getSortedPluginButtons('toolbar').slice(0, 5);
        },
        
        // Computed: Hidden plugin buttons (overflow into "More" menu)
        get hiddenPluginButtons() {
            return this.getSortedPluginButtons('toolbar').slice(5);
        },

        get pluginWorkspaceCollections() {
            const collections = new Map();
            for (const definition of Object.values(this.pluginWorkspaceDefinitions)) {
                const collection = definition.collection;
                if (!collection) continue;
                const plugin = this.installedPlugins?.find(
                    item => item.id === definition.pluginId
                );
                if (plugin?.enabled === false) continue;
                if (!collections.has(collection.id)) {
                    collections.set(collection.id, {
                        id: collection.id,
                        title: collection.title,
                        icon: collection.icon,
                        order: collection.order,
                        panels: []
                    });
                }
                collections.get(collection.id).panels.push({
                    pluginId: definition.pluginId,
                    panelId: definition.id,
                    title: definition.title,
                    icon: this.pluginWorkspacePanelIcon(
                        definition.pluginId,
                        definition.id,
                        definition.icon
                    ),
                    order: collection.tabOrder
                });
            }
            return [...collections.values()]
                .map(collection => ({
                    ...collection,
                    panels: collection.panels.sort(
                        (a, b) => a.order - b.order
                            || `${a.pluginId}:${a.panelId}`.localeCompare(
                                `${b.pluginId}:${b.panelId}`
                            )
                    )
                }))
                .sort((a, b) => a.order - b.order || a.id.localeCompare(b.id));
        },
        
        // Get localized button label
        getPluginButtonLabel(btn) {
            const lang = this.lang || 'en';
            return btn.label?.[lang] || btn.label?.en || btn.id;
        },

        getPluginWorkspaceCollection(collectionId) {
            return this.pluginWorkspaceCollections.find(
                collection => collection.id === collectionId
            ) || null;
        },

        activePluginWorkspaceCollectionPanels() {
            return this.getPluginWorkspaceCollection(
                this.pluginWorkspace.collectionId
            )?.panels || [];
        },

        switchPluginWorkspaceCollectionPanel(panel) {
            const collection = this.getPluginWorkspaceCollection(
                this.pluginWorkspace.collectionId
            );
            if (!collection?.panels.some(item => (
                item.pluginId === panel?.pluginId
                && item.panelId === panel?.panelId
            ))) {
                throw new Error('Plugin Workspace collection panel mismatch');
            }
            return this.openPluginWorkspacePanel(
                panel.panelId,
                { placement: 'main' },
                panel.pluginId
            );
        },

        pluginWorkspaceKey(pluginId, panelId) {
            return `${pluginId}:${panelId}`;
        },

        assertPluginWorkspaceOwner(pluginId) {
            if (typeof pluginId !== 'string' || !pluginId.trim()) {
                throw new TypeError('Plugin Workspace requires an explicit pluginId');
            }
            const plugin = this.installedPlugins.find(item => item.id === pluginId);
            if (!plugin || plugin.enabled === false) {
                throw new Error(`Plugin Workspace owner is not enabled: ${pluginId}`);
            }
            return pluginId;
        },

        assertPluginWorkspaceTransitionAvailable() {
            if (this._pluginWorkspaceTransition) {
                throw new Error(
                    'Plugin Workspace lifecycle cannot change during '
                    + this._pluginWorkspaceTransition
                );
            }
        },

        restorePluginWorkspaceFocus(returnFocus) {
            if (!returnFocus?.isConnected) return;
            this.$nextTick(() => {
                requestAnimationFrame(() => {
                    if (
                        !this.pluginWorkspace.show
                        && returnFocus.isConnected
                    ) {
                        returnFocus.focus();
                    }
                });
            });
        },

        validatePluginWorkspaceDefinition(definition) {
            const allowedKeys = new Set([
                'id',
                'title',
                'icon',
                'placements',
                'defaultPlacement',
                'collection',
                'mount'
            ]);
            if (
                !definition
                || typeof definition !== 'object'
                || Array.isArray(definition)
                || Object.keys(definition).some(key => !allowedKeys.has(key))
                || typeof definition.id !== 'string'
                || !PLUGIN_WORKSPACE_PANEL_ID_PATTERN.test(definition.id)
                || !definition.title
                || !definition.icon
                || !/^ri-[a-z0-9-]+$/.test(definition.icon)
                || !Array.isArray(definition.placements)
                || definition.placements.length === 0
                || new Set(definition.placements).size !== definition.placements.length
                || definition.placements.some(
                    placement => !PLUGIN_WORKSPACE_PLACEMENTS.includes(placement)
                )
                || !definition.placements.includes(definition.defaultPlacement)
                || typeof definition.mount !== 'function'
            ) {
                throw new TypeError('Invalid Plugin Workspace definition');
            }
            if (
                typeof definition.title !== 'string'
                && (
                    typeof definition.title !== 'object'
                    || Array.isArray(definition.title)
                    || Object.keys(definition.title).length === 0
                    || !Object.values(definition.title).every(
                        value => typeof value === 'string'
                    )
                    || !Object.values(definition.title).some(
                        value => value.trim()
                    )
                )
            ) {
                throw new TypeError('Invalid Plugin Workspace title');
            }
            if (definition.collection !== undefined) {
                const collection = definition.collection;
                const allowedCollectionKeys = new Set([
                    'id',
                    'title',
                    'icon',
                    'order',
                    'tabOrder'
                ]);
                if (
                    !collection
                    || typeof collection !== 'object'
                    || Array.isArray(collection)
                    || Object.keys(collection).some(
                        key => !allowedCollectionKeys.has(key)
                    )
                    || typeof collection.id !== 'string'
                    || !PLUGIN_WORKSPACE_PANEL_ID_PATTERN.test(collection.id)
                    || !collection.title
                    || typeof collection.icon !== 'string'
                    || !/^ri-[a-z0-9-]+$/.test(collection.icon)
                    || !Number.isFinite(collection.order)
                    || !Number.isFinite(collection.tabOrder)
                    || definition.defaultPlacement !== 'main'
                    || !definition.placements.includes('main')
                ) {
                    throw new TypeError(
                        'Invalid Plugin Workspace collection definition'
                    );
                }
                if (
                    typeof collection.title !== 'string'
                    && (
                        typeof collection.title !== 'object'
                        || Array.isArray(collection.title)
                        || Object.keys(collection.title).length === 0
                        || !Object.values(collection.title).every(
                            value => typeof value === 'string'
                        )
                        || !Object.values(collection.title).some(
                            value => value.trim()
                        )
                    )
                ) {
                    throw new TypeError(
                        'Invalid Plugin Workspace collection title'
                    );
                }
                const localizedSignature = value => (
                    typeof value === 'string'
                        ? value
                        : JSON.stringify(
                            Object.fromEntries(
                                Object.entries(value).sort(([a], [b]) => (
                                    a.localeCompare(b)
                                ))
                            )
                        )
                );
                const conflict = Object.values(
                    this.pluginWorkspaceDefinitions
                ).find(existing => (
                    existing.collection?.id === collection.id
                    && (
                        existing.collection.icon !== collection.icon
                        || existing.collection.order !== collection.order
                        || localizedSignature(existing.collection.title)
                            !== localizedSignature(collection.title)
                    )
                ));
                if (conflict) {
                    throw new Error(
                        `Plugin Workspace collection metadata mismatch: ${collection.id}`
                    );
                }
            }
            return definition;
        },

        focusPluginWorkspaceTitle(owner, panelId, placement) {
            this.$nextTick(() => {
                requestAnimationFrame(() => {
                    if (
                        this.pluginWorkspace.show
                        && this.pluginWorkspace.pluginId === owner
                        && this.pluginWorkspace.panelId === panelId
                        && this.pluginWorkspace.placement === placement
                    ) {
                        document.getElementById(
                            'plugin-workspace-title'
                        )?.focus();
                    }
                });
            });
        },

        registerPluginWorkspacePanel(definition, pluginId) {
            this.assertPluginWorkspaceTransitionAvailable();
            const owner = this.assertPluginWorkspaceOwner(pluginId);
            this.validatePluginWorkspaceDefinition(definition);
            const key = this.pluginWorkspaceKey(owner, definition.id);
            if (
                this.pluginWorkspace.show
                && this.pluginWorkspace.pluginId === owner
                && this.pluginWorkspace.panelId === definition.id
            ) {
                const disposeError = this.teardownPluginWorkspace();
                if (disposeError) throw disposeError;
            }
            this.pluginWorkspaceDefinitions[key] = Object.freeze({
                pluginId: owner,
                id: definition.id,
                title: definition.title,
                icon: definition.icon,
                placements: Object.freeze([...definition.placements]),
                defaultPlacement: definition.defaultPlacement,
                collection: definition.collection
                    ? Object.freeze({
                        id: definition.collection.id,
                        title: definition.collection.title,
                        icon: definition.collection.icon,
                        order: definition.collection.order,
                        tabOrder: definition.collection.tabOrder
                    })
                    : null,
                mount: definition.mount
            });
            this.recomputeFeatureCatalogRuntime();
            return true;
        },

        unregisterPluginWorkspacePanel(panelId, pluginId) {
            this.assertPluginWorkspaceTransitionAvailable();
            const owner = this.assertPluginWorkspaceOwner(pluginId);
            if (
                typeof panelId !== 'string'
                || !PLUGIN_WORKSPACE_PANEL_ID_PATTERN.test(panelId)
            ) {
                throw new TypeError('Invalid Plugin Workspace panelId');
            }
            const key = this.pluginWorkspaceKey(owner, panelId);
            if (!this.pluginWorkspaceDefinitions[key]) return false;
            if (
                this.pluginWorkspace.show
                && this.pluginWorkspace.pluginId === owner
                && this.pluginWorkspace.panelId === panelId
            ) {
                const disposeError = this.teardownPluginWorkspace();
                if (disposeError) throw disposeError;
            }
            delete this.pluginWorkspaceDefinitions[key];
            this.recomputeFeatureCatalogRuntime();
            return true;
        },

        openPluginWorkspacePanel(panelId, options, pluginId) {
            this.assertPluginWorkspaceTransitionAvailable();
            const owner = this.assertPluginWorkspaceOwner(pluginId);
            if (
                typeof panelId !== 'string'
                || !PLUGIN_WORKSPACE_PANEL_ID_PATTERN.test(panelId)
                || (options !== undefined && (
                    !options
                    || typeof options !== 'object'
                    || Array.isArray(options)
                    || Object.keys(options).some(key => key !== 'placement')
                ))
            ) {
                throw new TypeError('Invalid Plugin Workspace open request');
            }
            const key = this.pluginWorkspaceKey(owner, panelId);
            const definition = this.pluginWorkspaceDefinitions[key];
            if (!definition) {
                throw new Error(`Plugin Workspace panel is not registered: ${panelId}`);
            }
            const hasExplicitPlacement = (
                options !== undefined
                && Object.prototype.hasOwnProperty.call(options, 'placement')
            );
            const placement = hasExplicitPlacement
                ? options.placement
                : definition.defaultPlacement;
            if (!definition.placements.includes(placement)) {
                throw new TypeError(`Unsupported Plugin Workspace placement: ${placement}`);
            }
            const activation = this._pluginWorkspaceActivation;
            const shouldMoveFocus = (
                activation?.pluginId === owner
                && navigator.userActivation?.isActive === true
                && activation.trigger instanceof HTMLElement
                && activation.trigger.isConnected
            );
            const previousReturnFocus = this._pluginWorkspaceReturnFocus;
            const returnFocus = shouldMoveFocus
                ? activation.trigger
                : previousReturnFocus?.isConnected
                    ? previousReturnFocus
                    : null;
            if (
                this.pluginWorkspace.show
                && this.pluginWorkspace.pluginId === owner
                && this.pluginWorkspace.panelId === panelId
                && this.pluginWorkspace.placement === placement
            ) {
                if (shouldMoveFocus) {
                    this._pluginWorkspaceReturnFocus = returnFocus;
                    this.focusPluginWorkspaceTitle(
                        owner,
                        panelId,
                        placement
                    );
                }
                return true;
            }
            if (this.pluginWorkspace.show) {
                const disposeError = this.teardownPluginWorkspace(false);
                if (disposeError) {
                    this.restorePluginWorkspaceFocus(returnFocus);
                    throw disposeError;
                }
            }
            const container = document.getElementById('plugin-workspace-mount');
            if (!container) {
                this.restorePluginWorkspaceFocus(returnFocus);
                throw new Error('Plugin Workspace mount container is unavailable');
            }
            this._pluginWorkspaceReturnFocus = returnFocus;
            container.replaceChildren();
            this.pluginWorkspace = {
                show: true,
                pluginId: owner,
                panelId,
                title: definition.title,
                icon: definition.icon,
                collectionId: definition.collection?.id || null,
                collectionTitle: definition.collection?.title || null,
                collectionIcon: definition.collection?.icon || '',
                placement,
                dispose: null
            };
            try {
                this._pluginWorkspaceTransition = 'mount';
                const dispose = definition.mount({ container, placement });
                if (typeof dispose !== 'function') {
                    throw new TypeError(
                        'Plugin Workspace mount must synchronously return dispose()'
                    );
                }
                this.pluginWorkspace.dispose = dispose;
            } catch (error) {
                container.replaceChildren();
                this.pluginWorkspace = {
                    show: false,
                    pluginId: null,
                    panelId: null,
                    title: null,
                    icon: '',
                    collectionId: null,
                    collectionTitle: null,
                    collectionIcon: '',
                    placement: null,
                    dispose: null
                };
                const returnFocus = this._pluginWorkspaceReturnFocus;
                this._pluginWorkspaceReturnFocus = null;
                this.restorePluginWorkspaceFocus(returnFocus);
                throw error;
            } finally {
                this._pluginWorkspaceTransition = null;
            }
            if (shouldMoveFocus) {
                this.focusPluginWorkspaceTitle(
                    owner,
                    panelId,
                    placement
                );
            }
            return true;
        },

        teardownPluginWorkspace(restoreFocus = true) {
            this.assertPluginWorkspaceTransitionAvailable();
            if (!this.pluginWorkspace.show) return null;
            const dispose = this.pluginWorkspace.dispose;
            this.pluginWorkspace.dispose = null;
            let disposeError = null;
            try {
                this._pluginWorkspaceTransition = 'dispose';
                const disposeResult = dispose?.();
                if (disposeResult !== undefined) {
                    if (
                        disposeResult !== null
                        && (
                            typeof disposeResult === 'object'
                            || typeof disposeResult === 'function'
                        )
                        && typeof disposeResult.then === 'function'
                    ) {
                        Promise.resolve(disposeResult).catch(error => {
                            console.error(
                                '[Plugin Workspace async dispose]',
                                error
                            );
                        });
                    }
                    throw new TypeError(
                        'Plugin Workspace dispose must complete synchronously '
                        + 'and return undefined'
                    );
                }
            } catch (error) {
                disposeError = error;
            } finally {
                this._pluginWorkspaceTransition = null;
            }
            document.getElementById('plugin-workspace-mount')?.replaceChildren();
            this.pluginWorkspace = {
                show: false,
                pluginId: null,
                panelId: null,
                title: null,
                icon: '',
                collectionId: null,
                collectionTitle: null,
                collectionIcon: '',
                placement: null,
                dispose: null
            };
            const returnFocus = this._pluginWorkspaceReturnFocus;
            this._pluginWorkspaceReturnFocus = null;
            if (restoreFocus) {
                this.restorePluginWorkspaceFocus(returnFocus);
            }
            return disposeError;
        },

        closeActivePluginWorkspace() {
            const disposeError = this.teardownPluginWorkspace();
            if (disposeError) {
                console.error('[Plugin Workspace dispose]', disposeError);
            }
        },

        closePluginWorkspacePanel(panelId, pluginId) {
            this.assertPluginWorkspaceTransitionAvailable();
            const owner = this.assertPluginWorkspaceOwner(pluginId);
            if (
                typeof panelId !== 'string'
                || !PLUGIN_WORKSPACE_PANEL_ID_PATTERN.test(panelId)
            ) {
                throw new TypeError('Invalid Plugin Workspace panelId');
            }
            if (!this.pluginWorkspace.show) return false;
            if (
                this.pluginWorkspace.pluginId !== owner
                || this.pluginWorkspace.panelId !== panelId
            ) {
                throw new Error('Plugin Workspace ownership mismatch');
            }
            const disposeError = this.teardownPluginWorkspace();
            if (disposeError) throw disposeError;
            return true;
        },

        unregisterPluginWorkspacePanels(pluginId) {
            if (this.pluginWorkspace.pluginId === pluginId) {
                const disposeError = this.teardownPluginWorkspace();
                if (disposeError) {
                    console.error('[Plugin Workspace dispose]', disposeError);
                }
            }
            const prefix = `${pluginId}:`;
            for (const key of Object.keys(this.pluginWorkspaceDefinitions)) {
                if (key.startsWith(prefix)) {
                    delete this.pluginWorkspaceDefinitions[key];
                }
            }
            this.recomputeFeatureCatalogRuntime();
        },
        
        // Handle plugin button click
        async handlePluginButtonClick(btn, trigger = null) {
            if (btn.loading || btn.disabled) return false;
            try {
                const activation = (
                    navigator.userActivation?.isActive === true
                    && trigger instanceof HTMLElement
                    && trigger.isConnected
                ) ? {
                    pluginId: btn.pluginId,
                    trigger
                } : null;
                const previousActivation = this._pluginWorkspaceActivation;
                let clickResult;
                this._pluginWorkspaceActivation = activation;
                try {
                    clickResult = btn.onClick?.(btn);
                } finally {
                    this._pluginWorkspaceActivation = previousActivation;
                }
                await clickResult;
                return true;
            } catch (error) {
                console.error(`[Plugin ${btn.pluginId}] Button click error:`, error);
                // Reset loading state on error
                btn.loading = false;
                return false;
            }
        },

        async handlePluginMoreButtonClick(btn, trigger = null) {
            if (await this.handlePluginButtonClick(btn, trigger)) {
                this.showPluginMoreMenu = false;
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

            const moduleResponseError = async (
                response,
                fallbackMessage,
                fallbackCode
            ) => {
                let payload = null;
                try {
                    payload = await response.json();
                } catch (_error) {
                    payload = null;
                }
                return new ModuleSdkError(
                    payload?.detail || fallbackMessage,
                    payload?.code || fallbackCode,
                    response.status
                );
            };

            const taskPath = taskId => (
                `/api/module-tasks/${encodeURIComponent(taskId)}`
            );

            const taskResourcePath = (taskId, resourceRef, disposition) => {
                if (
                    typeof taskId !== 'string'
                    || !taskId
                    || typeof resourceRef !== 'string'
                    || !resourceRef
                ) {
                    throw new ModuleSdkError(
                        'taskId and resourceRef are required',
                        'invalid_sdk_argument',
                        0
                    );
                }
                return (
                    `${taskPath(taskId)}/resources/`
                    + `${encodeURIComponent(resourceRef)}`
                    + `?disposition=${encodeURIComponent(disposition)}`
                );
            };

            const taskResourceMetadata = (response, errorCode) => {
                const disposition =
                    response.headers.get('content-disposition') || '';
                const dispositionType = (
                    disposition.split(';', 1)[0] || ''
                ).trim().toLowerCase();
                const encoded = disposition.match(
                    /filename\*=UTF-8''([^;]+)/i
                );
                const quoted = disposition.match(/filename="([^"]+)"/i);
                let filename = quoted?.[1];
                if (encoded) {
                    try {
                        filename = decodeURIComponent(encoded[1]);
                    } catch (_error) {
                        filename = null;
                    }
                }
                const mime = (
                    response.headers.get('content-type') || ''
                ).split(';', 1)[0].trim();
                const sizeHeader = response.headers.get('content-length');
                const size = sizeHeader === null ? NaN : Number(sizeHeader);
                if (
                    !filename
                    || !mime
                    || !Number.isSafeInteger(size)
                    || size < 0
                    || !['inline', 'attachment'].includes(dispositionType)
                ) {
                    throw new ModuleSdkError(
                        'Task resource metadata is invalid',
                        errorCode,
                        502
                    );
                }
                return {
                    filename,
                    mime,
                    size,
                    disposition: dispositionType
                };
            };

            const probeTaskResourceMetadata = async (
                response,
                errorCode
            ) => {
                try {
                    return taskResourceMetadata(response, errorCode);
                } finally {
                    if (response.body) {
                        await response.body.cancel();
                    }
                }
            };

            const isTaskInputResource = payload => {
                if (
                    !payload
                    || typeof payload !== 'object'
                    || Array.isArray(payload)
                ) {
                    return false;
                }
                const expectedKeys = [
                    'resource_id',
                    'filename',
                    'media_type',
                    'size',
                    'sha256',
                    'expires_at'
                ];
                const keys = Object.keys(payload).sort();
                if (
                    keys.length !== expectedKeys.length
                    || !expectedKeys.sort().every(
                        (key, index) => keys[index] === key
                    )
                ) {
                    return false;
                }
                return (
                    typeof payload.resource_id === 'string'
                    && payload.resource_id.length > 0
                    && typeof payload.filename === 'string'
                    && payload.filename.length > 0
                    && typeof payload.media_type === 'string'
                    && payload.media_type.length > 0
                    && Number.isSafeInteger(payload.size)
                    && payload.size >= 0
                    && typeof payload.sha256 === 'string'
                    && /^[0-9a-f]{64}$/.test(payload.sha256)
                    && typeof payload.expires_at === 'string'
                    && /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})$/.test(
                        payload.expires_at
                    )
                    && !Number.isNaN(Date.parse(payload.expires_at))
                );
            };

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
                                        || (
                                            event.event === 'task.status'
                                            && MODULE_TERMINAL_STATES.has(
                                                event.data?.state
                                            )
                                        )
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
                                    taskView.error = {
                                        code: error?.code
                                            || 'module_event_stream_failed'
                                    };
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

            const createIdempotencyKey = () => {
                if (typeof crypto.randomUUID === 'function') {
                    return crypto.randomUUID();
                }
                const bytes = crypto.getRandomValues(new Uint8Array(16));
                bytes[6] = (bytes[6] & 0x0f) | 0x40;
                bytes[8] = (bytes[8] & 0x3f) | 0x80;
                const hex = Array.from(
                    bytes,
                    value => value.toString(16).padStart(2, '0')
                ).join('');
                return [
                    hex.slice(0, 8),
                    hex.slice(8, 12),
                    hex.slice(12, 16),
                    hex.slice(16, 20),
                    hex.slice(20)
                ].join('-');
            };

            const modulesSdk = Object.freeze({
                version: MODULE_SDK_VERSION,
                getFeatureStatus: moduleId => moduleRequest(
                    `/api/module-features/${encodeURIComponent(moduleId)}`
                ),
                uploadTaskResource: async file => {
                    if (
                        !(file instanceof Blob)
                        || typeof file.name !== 'string'
                        || !file.name
                    ) {
                        throw new ModuleSdkError(
                            'file is required',
                            'invalid_sdk_argument',
                            0
                        );
                    }
                    const form = new FormData();
                    form.append('file', file, file.name);
                    const response = await fetch('/api/module-task-resources', {
                        method: 'POST',
                        credentials: 'same-origin',
                        body: form
                    });
                    let payload = null;
                    try {
                        payload = await response.json();
                    } catch (_error) {}
                    if (!response.ok) {
                        throw new ModuleSdkError(
                            payload?.detail || 'Task resource upload failed',
                            payload?.code || 'task_resource_upload_failed',
                            response.status
                        );
                    }
                    if (!isTaskInputResource(payload)) {
                        throw new ModuleSdkError(
                            'Task resource upload response is invalid',
                            'task_resource_upload_response_invalid',
                            502
                        );
                    }
                    return payload;
                },
                startTask: async (request, options = {}) => {
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
                    if (
                        !options
                        || typeof options !== 'object'
                        || Array.isArray(options)
                        || Object.keys(options).some(
                            key => key !== 'presentation'
                        )
                        || ![
                            'task_center',
                            'embedded',
                            'conversation'
                        ].includes(
                            options.presentation || 'task_center'
                        )
                    ) {
                        throw new ModuleSdkError(
                            'presentation must be task_center, embedded, or conversation',
                            'invalid_sdk_argument',
                            0
                        );
                    }
                    const presentation = (
                        options.presentation || 'task_center'
                    );
                    if (
                        presentation === 'conversation'
                        && (
                            typeof request.chat_id !== 'string'
                            || !request.chat_id
                            || typeof request.user_message !== 'string'
                            || !request.user_message.trim()
                        )
                    ) {
                        throw new ModuleSdkError(
                            'conversation presentation requires chat_id and user_message',
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
                        'resource_ids',
                        'active_skill_ids'
                    ]) {
                        if (request[key] !== undefined) payload[key] = request[key];
                    }
                    const idempotencyKey = request.idempotency_key
                        || createIdempotencyKey();
                    const task = await moduleRequest('/api/module-tasks', {
                        method: 'POST',
                        headers: {
                            'Content-Type': 'application/json',
                            'Idempotency-Key': idempotencyKey
                        },
                        body: JSON.stringify(payload)
                    });
                    if (presentation === 'task_center') {
                        appInstance.rememberModuleTask(task.task_id);
                    }
                    appInstance.upsertModuleTask(task, {
                        select: presentation === 'task_center',
                        presentation
                    });
                    if (presentation === 'conversation') {
                        appInstance.attachConversationTask(
                            task,
                            request.user_message
                        );
                    }
                    if (
                        presentation === 'task_center'
                        || presentation === 'conversation'
                    ) {
                        subscribe(task.task_id);
                    }
                    return task;
                },
                listTasks: async (filters = {}) => {
                    if (
                        !filters
                        || typeof filters !== 'object'
                        || Array.isArray(filters)
                        || Object.keys(filters).some(
                            key => ![
                                'module_id',
                                'action_id',
                                'state',
                                'chat_id',
                                'limit'
                            ].includes(key)
                        )
                    ) {
                        throw new ModuleSdkError(
                            'Task filters are invalid',
                            'invalid_sdk_argument',
                            0
                        );
                    }
                    const query = new URLSearchParams();
                    for (const key of [
                        'module_id',
                        'action_id',
                        'state',
                        'chat_id'
                    ]) {
                        if (filters[key] === undefined) continue;
                        if (
                            typeof filters[key] !== 'string'
                            || !filters[key]
                        ) {
                            throw new ModuleSdkError(
                                'Task filters are invalid',
                                'invalid_sdk_argument',
                                0
                            );
                        }
                        query.set(key, filters[key]);
                    }
                    if (filters.limit !== undefined) {
                        if (
                            !Number.isInteger(filters.limit)
                            || filters.limit < 1
                            || filters.limit > 100
                        ) {
                            throw new ModuleSdkError(
                                'Task limit is invalid',
                                'invalid_sdk_argument',
                                0
                            );
                        }
                        query.set('limit', String(filters.limit));
                    }
                    const suffix = query.size ? `?${query}` : '';
                    const result = await moduleRequest(
                        `/api/module-tasks${suffix}`
                    );
                    return result.tasks;
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
                },
                getTaskResourceView: async (taskId, resourceRef) => {
                    const url = taskResourcePath(
                        taskId,
                        resourceRef,
                        'inline'
                    );
                    const response = await fetch(url, {
                        method: 'GET',
                        credentials: 'same-origin'
                    });
                    if (!response.ok) {
                        throw await moduleResponseError(
                            response,
                            'Task resource view failed',
                            'task_resource_view_failed'
                        );
                    }
                    const metadata = await probeTaskResourceMetadata(
                        response,
                        'task_resource_view_failed'
                    );
                    if (metadata.disposition !== 'inline') {
                        throw new ModuleSdkError(
                            'Task resource is not available for browser preview',
                            'task_resource_preview_unavailable',
                            415
                        );
                    }
                    return { url, ...metadata };
                },
                downloadTaskResource: async (taskId, resourceRef) => {
                    const url = taskResourcePath(
                        taskId,
                        resourceRef,
                        'attachment'
                    );
                    const response = await fetch(url, {
                        method: 'GET',
                        credentials: 'same-origin'
                    });
                    if (!response.ok) {
                        throw await moduleResponseError(
                            response,
                            'Task resource download failed',
                            'task_resource_download_failed'
                        );
                    }
                    const metadata = await probeTaskResourceMetadata(
                        response,
                        'task_resource_download_failed'
                    );
                    const anchor = document.createElement('a');
                    anchor.href = url;
                    anchor.download = metadata.filename;
                    anchor.click();
                    return { filename: metadata.filename };
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
                
                // UI Extension API for toolbar buttons, modal, and workspace panels
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
                            // The four-page shell has no sidebar. Keep accepting
                            // legacy declarations, but render them in the only
                            // generic Plugin entry surface that still exists.
                            placement: 'toolbar',
                            status: config.status || null,
                            disabled: config.disabled === true,
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
                            if (state.disabled !== undefined) button.disabled = state.disabled === true;
                            if (state.status !== undefined) button.status = state.status;
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
                    },

                    registerWorkspacePanel: (definition, pluginId) => (
                        appInstance.registerPluginWorkspacePanel(
                            definition,
                            pluginId
                        )
                    ),

                    unregisterWorkspacePanel: (panelId, pluginId) => (
                        appInstance.unregisterPluginWorkspacePanel(
                            panelId,
                            pluginId
                        )
                    ),

                    openWorkspacePanel: (panelId, options, pluginId) => (
                        appInstance.openPluginWorkspacePanel(
                            panelId,
                            options,
                            pluginId
                        )
                    ),

                    closeWorkspacePanel: (panelId, pluginId) => (
                        appInstance.closePluginWorkspacePanel(
                            panelId,
                            pluginId
                        )
                    )
                }
            };

            // Load enabled plugins
            this.loadEnabledPlugins();
            this.initPluginRuntimeSync();
        },

        initPluginRuntimeSync() {
            if (this._pluginRuntimeSyncInitialized) return;
            this._pluginRuntimeSyncInitialized = true;

            const syncVisibleTab = () => {
                if (document.visibilityState === 'visible') {
                    void this.syncPluginRuntimes();
                }
            };
            if (typeof window.addEventListener === 'function') {
                window.addEventListener('focus', syncVisibleTab);
            }
            if (
                typeof document !== 'undefined'
                && typeof document.addEventListener === 'function'
            ) {
                document.addEventListener('visibilitychange', syncVisibleTab);
            }

            if (typeof window.BroadcastChannel === 'function') {
                this._pluginRuntimeChangeChannel = new window.BroadcastChannel(
                    'chatraw-plugin-runtime-v1'
                );
                this._pluginRuntimeChangeChannel.addEventListener(
                    'message',
                    event => {
                        if (event.data?.type === 'plugins-changed') {
                            void this.syncPluginRuntimes();
                        }
                    }
                );
            }
        },

        announcePluginRuntimeChange(pluginId) {
            this._pluginRuntimeChangeChannel?.postMessage({
                type: 'plugins-changed',
                plugin_id: pluginId
            });
        },

        async refreshFeatureCatalogAfterPluginChange(pluginId) {
            await this.loadFeatureCatalog();
            this.announcePluginRuntimeChange(pluginId);
        },

        async syncPluginRuntimes() {
            if (this._pluginRuntimeSyncPromise) {
                return this._pluginRuntimeSyncPromise;
            }
            this._pluginRuntimeSyncPromise = (async () => {
                const response = await fetch('/api/plugins', {
                    credentials: 'same-origin',
                    cache: 'no-store'
                });
                if (!response.ok) return;

                const latestPlugins = await response.json();
                const latestById = new Map(
                    latestPlugins.map(plugin => [plugin.id, plugin])
                );
                for (const pluginId of Object.keys(this.pluginRuntimeVersions)) {
                    const latest = latestById.get(pluginId);
                    if (!latest || latest.enabled === false) {
                        this.cleanupPluginRuntime(pluginId);
                    }
                }

                this.installedPlugins = latestPlugins;
                for (const plugin of latestPlugins) {
                    if (plugin.enabled === false) continue;
                    const loadedVersion = this.pluginRuntimeVersions[plugin.id];
                    const currentVersion = String(plugin.version || '0');
                    if (loadedVersion !== currentVersion) {
                        await this.loadPluginJS(plugin);
                    }
                }
                this.recomputeFeatureCatalogRuntime();
            })().catch(error => {
                console.error('[Plugin] Failed to synchronize runtimes:', error);
            }).finally(() => {
                this._pluginRuntimeSyncPromise = null;
            });
            return this._pluginRuntimeSyncPromise;
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
                this.cleanupPluginRuntime(plugin.id);

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
                this.pluginRuntimeVersions[plugin.id] = String(
                    plugin.version || '0'
                );
                
                this._currentLoadingPlugin = null;
                console.log(`[Plugin] Loaded: ${plugin.id}`);
            } catch (e) {
                this._currentLoadingPlugin = null;
                console.error(`[Plugin] Failed to load ${plugin.id}:`, e);
            }
        },

        cleanupPluginRuntime(pluginId) {
            delete this.pluginRuntimeVersions[pluginId];
            this.unregisterPluginHooks(pluginId);
            this.unregisterPluginCompletions(pluginId);
            this.pluginToolbarButtons = this.pluginToolbarButtons.filter(
                button => button.pluginId !== pluginId
            );
            if (this.pluginFullscreenModal?.pluginId === pluginId) {
                this.closePluginFullscreenModal();
            }
            this.unregisterPluginWorkspacePanels(pluginId);
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
                    await this.refreshFeatureCatalogAfterPluginChange(plugin.id);
                } else {
                    this.showToast(this.t('installFailed'), 'error');
                }
            } catch (e) {
                this.showToast(this.t('installFailed'), 'error');
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
                    await this.refreshFeatureCatalogAfterPluginChange(data.plugin_id);
                } else {
                    this.showToast(this.t('installFailed'), 'error');
                }
            } catch (e) {
                this.showToast(this.t('installFailed'), 'error');
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
                        this.cleanupPluginRuntime(plugin.id);
                        this.showToast(this.t('pluginDisabled'), 'success');
                    }
                    await this.refreshFeatureCatalogAfterPluginChange(plugin.id);
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
                const res = await fetch(`/api/plugins/${encodeURIComponent(plugin.id)}`, {
                    method: 'DELETE'
                });
                
                if (res.ok) {
                    this.cleanupPluginRuntime(plugin.id);
                    this.showPluginSettings = false;
                    this.currentPluginSettings = null;
                    this.showToast(this.t('uninstallSuccess'), 'success');
                    await this.loadInstalledPlugins();
                    await this.refreshFeatureCatalogAfterPluginChange(plugin.id);
                } else {
                    const data = await res.json().catch(() => ({}));
                    this.showToast(this.t('uninstallFailed'), 'error');
                }
            } catch (e) {
                this.showToast(this.t('uninstallFailed'), 'error');
            }
        }
    };
}
