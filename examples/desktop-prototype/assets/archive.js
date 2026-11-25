/* Write a small uncompressed ZIP of UTF-8 text files. */
(() => {
    const encoder = new TextEncoder();

    function crc32(bytes) {
        let crc = 0xffffffff;
        for (const byte of bytes) {
            crc ^= byte;
            for (let bit = 0; bit < 8; bit++) {
                crc = (crc >>> 1) ^ ((crc & 1) ? 0xedb88320 : 0);
            }
        }
        return (crc ^ 0xffffffff) >>> 0;
    }

    function header(size, signature) {
        const bytes = new Uint8Array(size);
        const view = new DataView(bytes.buffer);
        const word = (offset, value) => view.setUint16(offset, value, true);
        const dword = (offset, value) => view.setUint32(offset, value, true);
        dword(0, signature);
        return {bytes, word, dword};
    }

    function createStoredZip(entries) {
        const localParts = [];
        const directory = [];
        let offset = 0;
        let directorySize = 0;
        for (const [name, text] of entries) {
            const filename = encoder.encode(name);
            const body = encoder.encode(text);
            const crc = crc32(body);
            const local = header(30, 0x04034b50);
            local.word(4, 20);
            local.word(6, 0x0800);
            local.word(12, 33);
            local.dword(14, crc);
            local.dword(18, body.length);
            local.dword(22, body.length);
            local.word(26, filename.length);
            localParts.push(local.bytes, filename, body);

            const central = header(46, 0x02014b50);
            central.word(4, 20);
            central.word(6, 20);
            central.word(8, 0x0800);
            central.word(14, 33);
            central.dword(16, crc);
            central.dword(20, body.length);
            central.dword(24, body.length);
            central.word(28, filename.length);
            central.dword(42, offset);
            directory.push(central.bytes, filename);
            offset += local.bytes.length + filename.length + body.length;
            directorySize += central.bytes.length + filename.length;
        }
        const end = header(22, 0x06054b50);
        end.word(8, entries.length);
        end.word(10, entries.length);
        end.dword(12, directorySize);
        end.dword(16, offset);
        return new Blob([...localParts, ...directory, end.bytes], {type: 'application/zip'});
    }

    window.createStoredZip = createStoredZip;
})();
