'use strict';
async function send(path, data, providedKey) {
  const {key} = await chrome.storage.local.get('key');
  const token = providedKey || key;
  if (!token) throw Error('Paste the desktop connection key first.');
  let response;
  try {
    response = await fetch('http://127.0.0.1:8765/extension/' + path, {
      method: 'POST',
      headers: {Authorization: 'Bearer ' + token, 'Content-Type': 'application/json'},
      body: JSON.stringify(data),
      signal: AbortSignal.timeout(4000),
    });
  } catch {
    throw Error('Open Z’s Download Manager on this computer.');
  }
  const result = await response.json();
  if (!response.ok) throw Error(result.error);
}
chrome.runtime.onInstalled.addListener(() => {
  chrome.contextMenus.create({
    id: 'send-link', title: 'Send to Z’s Download Manager', contexts: ['link'],
    targetUrlPatterns: ['http://*/*', 'https://*/*'],
  });
  chrome.alarms.create('ping', {periodInMinutes: 1});
});
chrome.runtime.onStartup.addListener(() => chrome.alarms.create('ping', {periodInMinutes: 1}));
chrome.alarms.onAlarm.addListener(alarm => {
  if (alarm.name === 'ping') send('ping', {}).catch(() => {});
});
chrome.contextMenus.onClicked.addListener(async info => {
  if (info.menuItemId !== 'send-link' || !info.linkUrl) return;
  try {
    await send('send', {url: info.linkUrl});
    await chrome.storage.local.set({lastMessage: 'Link sent to the download queue.'});
    await chrome.action.setBadgeBackgroundColor({color: '#63458f'});
    await chrome.action.setBadgeText({text: '✓'});
  } catch (error) {
    await chrome.storage.local.set({lastMessage: error.message});
    await chrome.action.setBadgeBackgroundColor({color: '#a03654'});
    await chrome.action.setBadgeText({text: '!'});
  }
});
chrome.runtime.onMessage.addListener((message, sender, reply) => {
  if (sender.id !== chrome.runtime.id) return;
  (async () => {
    if (message.type === 'connect') {
      await send('ping', {}, message.key);
      await chrome.storage.local.set({key: message.key});
    } else if (message.type === 'send') {
      await send('send', {url: message.url});
    } else {
      await send('ping', {});
    }
    reply({ok: true});
  })().catch(error => reply({error: error.message}));
  return true;
});
