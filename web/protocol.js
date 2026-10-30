/**
 * ComProtocol implementation in JavaScript
 * Wire-accurate binary protocol framing for 0700-AAM
 * Magic: 0x4D 0x54 ('M', 'T')
 * CRC-8: Polynomial 0x31 (Init 0xFF)
 */

(function (root, factory) {
    if (typeof module === 'object' && module.exports) {
        module.exports = factory();
    } else {
        root.ComProtocol = factory();
    }
}(typeof self !== 'undefined' ? self : this, function () {
    const MAGIC_0 = 0x4D; // 'M'
    const MAGIC_1 = 0x54; // 'T'

    // CRC-8 table lookup (poly 0x31, MSB-first)
    const CRC_TABLE = new Uint8Array(256);
    for (let i = 0; i < 256; i++) {
        let curr = i;
        for (let j = 0; j < 8; j++) {
            if ((curr & 0x80) !== 0) {
                curr = ((curr << 1) ^ 0x31) & 0xFF;
            } else {
                curr = (curr << 1) & 0xFF;
            }
        }
        CRC_TABLE[i] = curr;
    }

    function calculateCrc(bytes, offset, length) {
        let crc = 0xFF;
        for (let i = 0; i < length; i++) {
            crc = CRC_TABLE[crc ^ bytes[offset + i]];
        }
        return crc;
    }

    const CommandId = {
        PAD_1: 0x01,
        PAD_16: 0x10,
        BANK_A: 0x11,
        BANK_B: 0x12,
        BANK_C: 0x13,
        BANK_D: 0x14,
        BANK_E: 0x15,
        BANK_F: 0x16,
        BANK_G: 0x17,
        BANK_H: 0x18,

        MAIN: 0x20,
        BROWSE: 0x21,
        TRACK_MIX: 0x22,
        TRACK_MUTE: 0x23,
        NEXT_SEQ: 0x24,
        TC: 0x25,
        SAMPLER: 0x26,
        SAMPLE_EDIT: 0x27,
        PROGRAM_EDIT: 0x28,
        MENU: 0x29,
        SHIFT: 0x2A,
        BACK: 0x2B,
        COPY: 0x2C,
        PLUS: 0x2D,
        MINUS: 0x2E,

        TAP_TEMPO: 0x30,
        NOTE_REPEAT: 0x31,
        STEP_SEQ: 0x32,

        JOG_CW: 0x35,
        JOG_CCW: 0x36,
        JOG_CLICK: 0x37,

        TOUCH_SLIDER: 0x38,

        QLINK_1: 0x40,
        QLINK_2: 0x41,
        QLINK_3: 0x42,
        QLINK_4: 0x43,

        REC: 0x50,
        OVERDUB: 0x51,
        STOP: 0x52,
        PLAY: 0x53,
        PLAY_START: 0x54,

        FULL_LEVEL: 0x55,
        LEVEL_16: 0x56,
        ERASE: 0x57,

        SET_PAD_COLOR: 0x60,
        SET_PAD_LED: 0x61,
        SET_BUTTON_LED: 0x62,
        SET_TOUCH_LED: 0x63,
        SET_LCD_TEXT: 0x64,
        SET_CV_GATE: 0x70
    };

    function encodePacket(cmd, payload = [], msgType = 0x01, dir = 0x01) {
        const payloadBytes = payload instanceof Uint8Array ? payload : new Uint8Array(payload);
        const len = payloadBytes.length;
        const totalLen = 7 + len;
        const buffer = new Uint8Array(totalLen);

        buffer[0] = MAGIC_0;
        buffer[1] = MAGIC_1;
        buffer[2] = msgType & 0xFF;
        buffer[3] = dir & 0xFF;
        buffer[4] = cmd & 0xFF;
        buffer[5] = len & 0xFF;

        for (let i = 0; i < len; i++) {
            buffer[6 + i] = payloadBytes[i];
        }

        // CRC over bytes 2 through 5+len
        const crc = calculateCrc(buffer, 2, 4 + len);
        buffer[6 + len] = crc;

        return buffer;
    }

    function decodePacket(buffer) {
        if (buffer.length < 7) return null;
        if (buffer[0] !== MAGIC_0 || buffer[1] !== MAGIC_1) return null;

        const msgType = buffer[2];
        const dir = buffer[3];
        const cmd = buffer[4];
        const len = buffer[5];

        if (buffer.length < 7 + len) return null;

        const expectedCrc = buffer[6 + len];
        const actualCrc = calculateCrc(buffer, 2, 4 + len);
        if (expectedCrc !== actualCrc) {
            console.warn(`[ComProtocol] CRC mismatch: expected 0x${expectedCrc.toString(16)}, got 0x${actualCrc.toString(16)}`);
            return null;
        }

        const payload = buffer.slice(6, 6 + len);
        return { msgType, dir, cmd, len, payload };
    }

    return {
        MAGIC_0,
        MAGIC_1,
        CommandId,
        calculateCrc,
        encodePacket,
        decodePacket
    };
}));
