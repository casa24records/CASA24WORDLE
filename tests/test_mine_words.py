"""The miner must output words only, and drop private or unsafe tokens."""

import docx

import mine_words

EMPTY_PDF = (
    b"%PDF-1.4\n1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj\n"
    b"2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj\n"
    b"3 0 obj<</Type/Page/Parent 2 0 R/MediaBox[0 0 200 200]>>endobj\n"
    b"trailer<</Root 1 0 R>>\n%%EOF\n"
)


def test_miner_filters(tmp_path):
    (tmp_path / "Reuniones").mkdir()
    (tmp_path / "Reuniones" / "semana.txt").write_text(
        "La plena quedó brutal, pura plena con priti vibes.\n"
        "Escríbele a kolox@gmail.com o mira https://lalal.com/abcde y @zorbo\n"
        "Password: 'blurf' y la clave es tripx\n"
        "Hablamos con Wendo y Wendo dijo que sí. Código QWXZT y ab12c\n",
        encoding="utf-8",
    )
    d = docx.Document()
    d.add_paragraph("Las notas de la canción tienen ritmo, mucho ritmo.")
    d.save(tmp_path / "Reuniones" / "notas.docx")
    (tmp_path / "Finanzas").mkdir()
    (tmp_path / "Finanzas" / "gastos.txt").write_text("monto saldo glorp", encoding="utf-8")
    (tmp_path / "scan.pdf").write_bytes(EMPTY_PDF)

    rows, needs_ocr, n_files, _ = mine_words.mine(str(tmp_path))
    words = {r["word"] for r in rows}

    # normal words from text and Word files are found
    assert {"quedó", "vibes", "ritmo"} <= words
    # words already in the Casa 24 lists are not suggested again
    assert not {"plena", "priti", "notas"} & words
    # unknown lowercase words go to the slang review pile
    assert next(r for r in rows if r["word"] == "vibes")["lang"] in ("unknown", "en")
    for private in ["kolox", "lalal", "abcde", "zorbo", "blurf", "tripx", "wendo", "qwxzt", "glorp", "saldo", "monto"]:
        assert private not in words, private
    assert any(p.endswith("scan.pdf") for p in needs_ocr)
    # output rows hold only these fields: no sentences, no file names
    assert all(set(r) == {"lang", "word", "count", "in_base_dictionary", "offensive", "decision"} for r in rows)
