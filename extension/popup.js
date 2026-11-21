'use strict';
const $ = id => document.getElementById(id);
async function request(type, data = {}) {
  const response = await chrome.runtime.sendMessage({type, ...data});
  if (!response.ok) throw Error(response.error);
}
function connection(connected, text) {
  $('status').textContent = text;
  $('status').dataset.connected = connected;
  $('connect').hidden = connected;
  $('send').hidden = $('pair').hidden = !connected;
}
$('pair').onclick = () => {
  $('connect').hidden = !$('connect').hidden;
  if (!$('connect').hidden) $('key').focus();
};
$('connect').onsubmit = async event => {
  event.preventDefault();
  try {
    await request('connect', {key: $('key').value.trim()});
    connection(true, '● Connected to desktop app');
    $('key').value = '';
    $('result').textContent = '';
  } catch (error) {
    connection(false, error.message);
  }
};
$('send').onsubmit = async event => {
  event.preventDefault();
  const button = event.target.querySelector('button');
  button.disabled = true;
  try {
    await request('send', {url: $('url').value});
    $('result').textContent = 'Link sent to the download queue.';
    $('url').value = '';
    connection(true, '● Connected to desktop app');
  } catch (error) {
    $('result').textContent = error.message;
  } finally {
    button.disabled = false;
  }
};
(async () => {
  const {lastMessage} = await chrome.storage.local.get('lastMessage');
  if (lastMessage) {
    $('result').textContent = lastMessage;
    await chrome.storage.local.remove('lastMessage');
  }
  await chrome.action.setBadgeText({text: ''});
  try {
    await request('ping');
    connection(true, '● Connected to desktop app');
  } catch (error) {
    connection(false, error.message);
  }
})();
