/**
 * Context Compressor Plugin for ChatRaw
 *
 * Provides a toolbar button for manual context compaction. Automatic compaction
 * is handled by the backend according to this plugin's enabled state and settings.
 *
 * @version 1.0.0
 * @author ChatRaw
 * @license MIT
 */
(function(ChatRaw) {
  'use strict';

  if (!ChatRaw || !ChatRaw.ui || !ChatRaw.ui.registerToolbarButton) {
    console.error('[ContextCompressor] ChatRawPlugin UI API not available');
    return;
  }

  const PLUGIN_ID = 'context-compressor';

  const i18n = {
    en: {
      buttonLabel: 'Compress Context',
      noChat: 'No active chat to compress',
      compacted: 'Context compressed',
      noNeed: 'No compaction needed',
      failed: 'Context compaction failed',
      savedTokens: 'tokens saved',
      messagesCovered: 'old messages covered'
    },
    zh: {
      buttonLabel: '压缩上下文',
      noChat: '当前没有可压缩的会话',
      compacted: '上下文已压缩',
      noNeed: '暂无需要压缩的内容',
      failed: '上下文压缩失败',
      savedTokens: '节省 token',
      messagesCovered: '条旧消息已覆盖'
    }
  };

  function t(key) {
    const lang = ChatRaw.utils?.getLanguage?.() || 'en';
    return i18n[lang]?.[key] || i18n.en[key] || key;
  }

  function displayError(error, fallbackKey) {
    const lang = ChatRaw.utils?.getLanguage?.() || 'en';
    if (lang === 'en') return error?.message || error || t(fallbackKey);
    return t(fallbackKey);
  }

  async function compactCurrentChat() {
    const chatId = ChatRaw.utils?.getCurrentChatId?.();
    if (!chatId) {
      ChatRaw.utils?.showToast?.(t('noChat'), 'info');
      return;
    }

    ChatRaw.ui.setButtonState('manual-compact', { loading: true }, PLUGIN_ID);
    try {
      const res = await fetch(`/api/chats/${encodeURIComponent(chatId)}/compact`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' }
      });
      const data = await res.json().catch(() => ({}));

      if (!res.ok || data.success === false) {
        throw new Error(data.error || res.statusText || t('failed'));
      }

      if (data.compressed) {
        const covered = data.compressed_message_count || 0;
        const saved = data.saved_tokens || 0;
        ChatRaw.utils?.showToast?.(
          `${t('compacted')}: ${covered} ${t('messagesCovered')}, ${saved} ${t('savedTokens')}`,
          'success'
        );
      } else {
        ChatRaw.utils?.showToast?.(displayError(data.message, 'noNeed'), 'info');
      }
    } catch (error) {
      console.error('[ContextCompressor] Manual compaction failed:', error);
      ChatRaw.utils?.showToast?.(displayError(error, 'failed'), 'error');
    } finally {
      ChatRaw.ui.setButtonState('manual-compact', { loading: false }, PLUGIN_ID);
    }
  }

  ChatRaw.ui.registerToolbarButton({
    id: 'manual-compact',
    icon: 'ri-collapse-horizontal-fill',
    label: {
      en: 'Compress Context',
      zh: '压缩上下文'
    },
    onClick: compactCurrentChat,
    order: 20
  }, PLUGIN_ID);

})(window.ChatRawPlugin);
