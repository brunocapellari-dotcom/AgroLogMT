from __future__ import annotations

import io
import unittest
import zipfile

from collector.xlsx_reader import read_xlsx


class XlsxReaderTests(unittest.TestCase):
    def _fixture(self) -> bytes:
        out = io.BytesIO()
        with zipfile.ZipFile(out, "w") as z:
            z.writestr("xl/workbook.xml", '''<?xml version="1.0" encoding="UTF-8"?>
            <workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"
              xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">
              <sheets><sheet name="Soja" sheetId="1" r:id="rId1"/></sheets>
            </workbook>''')
            z.writestr("xl/_rels/workbook.xml.rels", '''<?xml version="1.0" encoding="UTF-8"?>
            <Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
              <Relationship Id="rId1" Target="worksheets/sheet1.xml"
                Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet"/>
            </Relationships>''')
            z.writestr("xl/sharedStrings.xml", '''<?xml version="1.0" encoding="UTF-8"?>
            <sst xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" count="2" uniqueCount="2">
              <si><t>UF</t></si><si><t>MT</t></si>
            </sst>''')
            z.writestr("xl/worksheets/sheet1.xml", '''<?xml version="1.0" encoding="UTF-8"?>
            <worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">
              <sheetData>
                <row r="1"><c r="A1" t="s"><v>0</v></c><c r="B1" t="inlineStr"><is><t>Produção</t></is></c></row>
                <row r="2"><c r="A2" t="s"><v>1</v></c><c r="B2"><v>49200.5</v></c><c r="D2" t="b"><v>1</v></c></row>
              </sheetData>
            </worksheet>''')
        return out.getvalue()

    def test_reads_shared_inline_numeric_and_sparse_cells(self) -> None:
        sheets = read_xlsx(self._fixture())
        self.assertEqual(len(sheets), 1)
        self.assertEqual(sheets[0].name, "Soja")
        self.assertEqual(sheets[0].rows[0], ["UF", "Produção"])
        self.assertEqual(sheets[0].rows[1], ["MT", 49200.5, None, True])


if __name__ == "__main__":
    unittest.main()
