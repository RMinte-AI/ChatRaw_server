/**
 * CSV Parser Plugin for ChatRaw
 * Parses CSV/TSV files for AI reading
 * 
 * @version 1.0.0
 * @author ChatRaw
 * @license MIT
 */
(function(ChatRaw) {
    'use strict';
    
    // Safety check
    if (!ChatRaw || !ChatRaw.hooks) {
        console.error('[CSVParser] ChatRawPlugin not available');
        return;
    }

    const i18n = {
        en: {
            rowsTruncated: count => `*... ${count} more rows truncated*`,
            libraryMissing: 'Papa Parse library is unavailable. Please try again later.',
            invalidFile: 'Invalid file.',
            fileTooLarge: 'The file is too large. The maximum supported size is 10 MB.',
            parseError: 'The CSV file could not be parsed.',
            noData: 'No data was found in the CSV file.',
            noContent: 'No content could be extracted from the CSV file.',
            fileLabel: 'CSV File', rowsLabel: 'Rows', columnsLabel: 'Columns',
            parseFailed: 'Failed to parse the CSV file.'
        },
        zh: {
            rowsTruncated: count => `*……另有 ${count} 行数据未显示*`,
            libraryMissing: 'CSV 解析组件暂不可用，请稍后重试。',
            invalidFile: '文件无效。', fileTooLarge: '文件过大，最大支持 10 MB。',
            parseError: '无法解析此 CSV 文件。', noData: 'CSV 文件中没有可用数据。',
            noContent: '无法从 CSV 文件中提取内容。',
            fileLabel: 'CSV 文件', rowsLabel: '行数', columnsLabel: '列数',
            parseFailed: 'CSV 文件解析失败。'
        }
    };

    function t(key, ...args) {
        const lang = ChatRaw.utils?.getLanguage?.() || 'en';
        const value = i18n[lang]?.[key] ?? i18n.en[key] ?? key;
        return typeof value === 'function' ? value(...args) : value;
    }
    
    // Get Papa Parse library from dependencies
    let Papa = ChatRaw.require('papaparse');
    
    // Fallback: try window.Papa if not found in dependencies
    if (!Papa && typeof window !== 'undefined' && window.Papa) {
        Papa = window.Papa;
    }
    
    /**
     * Format parsed CSV data as Markdown table
     */
    function formatAsMarkdownTable(data) {
        if (!data || data.length === 0) return '';
        
        const rows = [];
        const MAX_ROWS = 1000;
        const MAX_CELL_LENGTH = 100;
        
        // First row as header
        const headers = data[0].map(h => {
            let val = String(h || '').trim();
            val = val.replace(/\|/g, '\\|').replace(/\n/g, ' ');
            if (val.length > MAX_CELL_LENGTH) val = val.substring(0, MAX_CELL_LENGTH) + '...';
            return val;
        });
        
        rows.push('| ' + headers.join(' | ') + ' |');
        rows.push('| ' + headers.map(() => '---').join(' | ') + ' |');
        
        // Data rows
        const maxRows = Math.min(data.length, MAX_ROWS + 1);
        for (let i = 1; i < maxRows; i++) {
            const row = data[i].map(cell => {
                let val = String(cell || '').trim();
                val = val.replace(/\|/g, '\\|').replace(/\n/g, ' ');
                if (val.length > MAX_CELL_LENGTH) val = val.substring(0, MAX_CELL_LENGTH) + '...';
                return val;
            });
            rows.push('| ' + row.join(' | ') + ' |');
        }
        
        if (data.length > MAX_ROWS + 1) {
            rows.push('');
            rows.push(t('rowsTruncated', data.length - MAX_ROWS - 1));
        }
        
        return rows.join('\n');
    }
    
    /**
     * Register the parse_document hook
     */
    ChatRaw.hooks.register('parse_document', {
        fileTypes: ['.csv', '.tsv'],
        priority: 10,
        
        handler: async (file) => {
            try {
                // Re-check Papa Parse availability
                let papaLib = Papa;
                if (!papaLib && ChatRaw.require) {
                    papaLib = ChatRaw.require('papaparse');
                }
                if (!papaLib && typeof window !== 'undefined' && window.Papa) {
                    papaLib = window.Papa;
                }
                
                if (!papaLib) {
                    return {
                        success: false,
                        error: t('libraryMissing')
                    };
                }
                
                // Validate file
                if (!file || typeof file.text !== 'function') {
                    return {
                        success: false,
                        error: t('invalidFile')
                    };
                }
                
                // Read file content
                const text = await file.text();
                
                // Check file size (limit to 10MB)
                if (text.length > 10 * 1024 * 1024) {
                    return {
                        success: false,
                        error: t('fileTooLarge')
                    };
                }
                
                // Determine delimiter for TSV files
                const filename = file.name?.toLowerCase() || '';
                const delimiter = filename.endsWith('.tsv') ? '\t' : '';  // Empty = auto-detect
                
                // Parse CSV
                const result = papaLib.parse(text, {
                    delimiter: delimiter,
                    header: false,
                    skipEmptyLines: true,
                    dynamicTyping: false
                });
                
                if (result.errors && result.errors.length > 0) {
                    const criticalErrors = result.errors.filter(e => e.type === 'Quotes');
                    if (criticalErrors.length > 0 && !result.data?.length) {
                        return {
                            success: false,
                            error: t('parseError')
                        };
                    }
                }
                
                if (!result.data || result.data.length === 0) {
                    return {
                        success: false,
                        error: t('noData')
                    };
                }
                
                // Format as Markdown table
                const content = formatAsMarkdownTable(result.data);
                
                if (!content) {
                    return {
                        success: false,
                        error: t('noContent')
                    };
                }
                
                // Build output with metadata
                const rowCount = result.data.length - 1;  // Minus header
                const colCount = result.data[0]?.length || 0;
                const header = `**${t('fileLabel')}**: ${file.name || 'data.csv'}\n**${t('rowsLabel')}**: ${rowCount}, **${t('columnsLabel')}**: ${colCount}\n\n`;
                
                return {
                    success: true,
                    content: header + content
                };
                
            } catch (error) {
                console.error('[CSVParser] Error:', error);
                return {
                    success: false,
                    error: t('parseFailed')
                };
            }
        }
    });
    
    // Log successful initialization
    console.log('[CSVParser] Plugin loaded successfully');
    
})(window.ChatRawPlugin);
