require('dotenv').config();

const express = require('express');
const axios = require('axios');
const qrcode = require('qrcode-terminal');
const QRCode = require('qrcode');

const {
    default: makeWASocket,
    DisconnectReason,
    useMultiFileAuthState,
} = require('@whiskeysockets/baileys');

const { Boom } = require('@hapi/boom');
const { useSupabaseAuthState } = require('./supabaseAuth');

const app = express();

app.use(express.json());

const PORT = process.env.PORT || 3001;
const DJANGO_URL = process.env.DJANGO_URL || 'http://127.0.0.1:8000';
const BRIDGE_API_KEY = process.env.BRIDGE_API_KEY || '';

let whatsappSocket = null;
let connectionStatus = 'starting';

// QR ya sasa kama picha (data URL) — inatumiwa na admin panel
let currentQrDataUrl = '';
let currentQrAt = 0;
let connectedNumber = '';
let clearAuthStore = null;


// ============================================================
// HEALTH CHECK
// ============================================================

app.get('/health', (req, res) => {
    res.json({
        success: true,
        service: 'Kilimoni WhatsApp Bridge',
        status: connectionStatus,
    });
});


// ============================================================
// STATUS
// ============================================================

app.get('/status', (req, res) => {
    res.json({
        success: true,
        status: connectionStatus,
        connected: connectionStatus === 'connected',
    });
});


// ============================================================
// QR CODE (kwa admin panel)
// ============================================================

app.get('/qr', (req, res) => {

    // QR ya Baileys huisha baada ya ~60s. Tukiwa na ya zamani
    // tunaionyesha kama imepitwa ili admin ajue kusubiri mpya.
    const ageSeconds = currentQrAt
        ? Math.round((Date.now() - currentQrAt) / 1000)
        : null;

    res.json({
        success: true,
        status: connectionStatus,
        connected: connectionStatus === 'connected',
        number: connectedNumber,
        qr: currentQrDataUrl,
        qr_age_seconds: ageSeconds,
        expired: ageSeconds !== null && ageSeconds > 60,
    });
});


// ============================================================
// LOGOUT (kuunganisha namba nyingine)
// ============================================================

app.post('/logout', async (req, res) => {

    if (req.headers['x-bridge-key'] !== BRIDGE_API_KEY) {
        return res.status(401).json({ success: false, error: 'Unauthorized' });
    }

    try {
        if (whatsappSocket) {
            await whatsappSocket.logout();
        }
        if (clearAuthStore) {
            await clearAuthStore();
        }
        connectionStatus = 'disconnected';
        connectedNumber = '';
        currentQrDataUrl = '';
        res.json({ success: true });
    } catch (e) {
        res.status(500).json({ success: false, error: String(e) });
    }
});


// ============================================================
// CONNECT TO WHATSAPP
// ============================================================

async function connectToWhatsApp() {

    // Supabase (Postgres) ikiwepo — session inabaki hata baada ya deploy.
    // Bila hiyo tunatumia folda (nzuri kwa local development).
    let state, saveCreds;

    if (process.env.DATABASE_URL) {

        const auth = await useSupabaseAuthState(
            process.env.DATABASE_URL,
            process.env.SESSION_NAME || 'kilimoni'
        );

        state = auth.state;
        saveCreds = auth.saveCreds;
        clearAuthStore = auth.clearAuth;

        console.log('Auth: Supabase (session inabaki baada ya deploy)');

    } else {

        const auth = await useMultiFileAuthState('./auth_info_baileys');

        state = auth.state;
        saveCreds = auth.saveCreds;
        clearAuthStore = null;

        console.log('Auth: folda ya ndani (local)');
    }

    console.log('');
    console.log('========================================');
    console.log('       KILIMONI WHATSAPP BOT');
    console.log('========================================');
    console.log('');

    const sock = makeWASocket({
        auth: state,

        markOnlineOnConnect: false,

        syncFullHistory: false,

        browser: ['Kilimoni', 'Chrome', '1.0.0'],
    });

    whatsappSocket = sock;


    // ========================================================
    // CONNECTION UPDATE
    // ========================================================

    sock.ev.on('connection.update', (update) => {

        const {
            connection,
            lastDisconnect,
            qr,
        } = update;


        // ----------------------------------------------------
        // QR CODE
        // ----------------------------------------------------

        if (qr) {

            console.log('');
            console.log('========================================');
            console.log('       SCAN THIS QR CODE');
            console.log('========================================');
            console.log('');

            qrcode.generate(qr, {
                small: true,
            });

            // Tengeneza picha ya QR kwa ajili ya admin panel
            QRCode.toDataURL(qr, { width: 320, margin: 2 })
                .then((url) => {
                    currentQrDataUrl = url;
                    currentQrAt = Date.now();
                    connectionStatus = 'waiting_qr';
                })
                .catch((err) => {
                    console.log('QR image error:', err.message);
                });

            console.log('');
            console.log('WhatsApp > Settings > Linked Devices');
            console.log('> Link a Device > Scan QR');
            console.log('');
        }


        // ----------------------------------------------------
        // CONNECTED
        // ----------------------------------------------------

        if (connection === 'open') {

            connectionStatus = 'connected';
            currentQrDataUrl = '';
            currentQrAt = 0;
            connectedNumber = (sock.user?.id || '').split(':')[0];

            console.log('');
            console.log('========================================');
            console.log('   WHATSAPP CONNECTED SUCCESSFULLY');
            console.log('========================================');
            console.log('');
        }


        // ----------------------------------------------------
        // CONNECTION CLOSED
        // ----------------------------------------------------

        if (connection === 'close') {

            connectionStatus = 'disconnected';

            const statusCode =
                new Boom(lastDisconnect?.error)?.output?.statusCode;

            const shouldReconnect =
                statusCode !== DisconnectReason.loggedOut;

            console.log('');
            console.log('WhatsApp connection closed.');
            console.log('Status code:', statusCode);
            console.log('Reconnect:', shouldReconnect);
            console.log('');

            if (shouldReconnect) {

                console.log('Reconnecting to WhatsApp...');

                setTimeout(() => {
                    connectToWhatsApp();
                }, 3000);
            } else {

                console.log('');
                console.log('WhatsApp session has been logged out.');
                console.log('');
                if (clearAuthStore) {
                    clearAuthStore().then(() => {
                        console.log('Session imefutwa — scan QR upya.');
                        setTimeout(() => connectToWhatsApp(), 2000);
                    });
                } else {
                    console.log(
                        'Delete the auth_info_baileys folder and scan QR again.'
                    );
                }
            }
        }
    });


    // ========================================================
    // SAVE WHATSAPP SESSION
    // ========================================================

    sock.ev.on('creds.update', saveCreds);


    // ========================================================
    // RECEIVE MESSAGES
    // ========================================================

    sock.ev.on('messages.upsert', async (event) => {

        if (event.type !== 'notify') {
            return;
        }


        for (const message of event.messages) {

            try {

                // Ignore messages sent by the bot itself
                if (message.key.fromMe) {
                    continue;
                }


                // Ignore status updates
                if (message.key.remoteJid === 'status@broadcast') {
                    continue;
                }


                // Ignore group messages for now
                const remoteJid = message.key.remoteJid || '';

                if (remoteJid.endsWith('@g.us')) {
                    console.log('Group message ignored.');
                    continue;
                }


                // ------------------------------------------------
                // GET PHONE NUMBER
                // ------------------------------------------------

                // WhatsApp sasa hutumia @lid (kitambulisho) badala ya
                // namba. Tunajaribu kupata namba halisi kwa njia mbili;
                // ikishindikana TUNAENDELEA kwa LID — bot haipaswi
                // kunyamaza kwa sababu ya kitambulisho.
                let sourceJid = remoteJid;
                let isLid = false;

                if (remoteJid.endsWith('@lid')) {

                    isLid = true;

                    let pn = message.key.senderPn || '';

                    // Njia ya pili: ramani ya LID -> namba ya Baileys
                    if (!pn) {
                        try {
                            pn = await sock.signalRepository
                                ?.lidMapping
                                ?.getPNForLID?.(remoteJid) || '';
                        } catch (e) {
                            pn = '';
                        }
                    }

                    if (pn) {
                        sourceJid = pn;
                        isLid = false;
                    }
                }

                const phone = sourceJid
                    .replace('@s.whatsapp.net', '')
                    .replace('@lid', '')
                    .replace(/\D/g, '');

                if (!phone) {
                    console.log('Hakuna kitambulisho — umerukwa:', remoteJid);
                    continue;
                }

                if (isLid) {
                    console.log(
                        'ONYO: namba halisi haipatikani, tunatumia LID:',
                        phone
                    );
                }


                // ------------------------------------------------
                // GET MESSAGE ID
                // ------------------------------------------------

                const messageId =
                    message.key.id || '';


                // ------------------------------------------------
                // GET TEXT
                // ------------------------------------------------

                let text = '';


                if (message.message?.conversation) {

                    text = message.message.conversation;

                } else if (
                    message.message?.extendedTextMessage?.text
                ) {

                    text =
                        message.message.extendedTextMessage.text;

                } else if (
                    message.message?.imageMessage?.caption
                ) {

                    text =
                        message.message.imageMessage.caption;

                } else if (
                    message.message?.videoMessage?.caption
                ) {

                    text =
                        message.message.videoMessage.caption;
                }


                text = text.trim();


                // ------------------------------------------------
                // IGNORE EMPTY MESSAGE
                // ------------------------------------------------

                if (!text) {

                    console.log(
                        'Received a non-text message from:',
                        phone
                    );

                    continue;
                }


                console.log('');
                console.log('----------------------------------------');
                console.log('Incoming WhatsApp message');
                console.log('Phone:', phone);
                console.log('Message:', text);
                console.log('Message ID:', messageId);
                console.log('----------------------------------------');
                console.log('');


                // ------------------------------------------------
                // SEND TO DJANGO
                // ------------------------------------------------

                const response = await axios.post(
                    
                `${DJANGO_URL}/webhook/baileys/incoming/`,
                {
                    phone: phone,
                    message: text,
                    message_id: messageId,
                },
                {
                    headers: {
                        'Content-Type': 'application/json',
                        'X-Bridge-Key': BRIDGE_API_KEY,
                    },

                    timeout: 120000,
                }
            );


                // ------------------------------------------------
                // GET DJANGO RESPONSE
                // ------------------------------------------------

                const reply =
                    response.data?.reply;


                if (!reply) {

                    console.log(
                        'Django did not return a reply.'
                    );

                    continue;
                }


                // ------------------------------------------------
                // SEND RESPONSE TO WHATSAPP
                // ------------------------------------------------

                await sock.sendMessage(
                    remoteJid,
                    {
                        text: String(reply),
                    }
                );


                console.log('');
                console.log('Reply sent successfully.');
                console.log('To:', phone);
                console.log('');
            }

            catch (error) {

                console.error('');
                console.error(
                    'Error processing WhatsApp message:'
                );

                if (error.response) {

                    console.error(
                        'Django status:',
                        error.response.status
                    );

                    console.error(
                        'Django response:',
                        error.response.data
                    );

                } else {

                    console.error(
                        error.message
                    );
                }

                console.error('');
            }
        }
    });
}


// ============================================================
// START EXPRESS SERVER
// ============================================================

app.listen(PORT, () => {

    console.log('');
    console.log('========================================');
    console.log('   KILIMONI WHATSAPP BRIDGE');
    console.log('========================================');
    console.log('');
    console.log(`Bridge running on port: ${PORT}`);
    console.log(`Django URL: ${DJANGO_URL}`);
    console.log('');
});


// ============================================================
// START WHATSAPP
// ============================================================

connectToWhatsApp().catch((error) => {

    console.error('');
    console.error(
        'Failed to start WhatsApp connection:'
    );

    console.error(error);

    process.exit(1);
});