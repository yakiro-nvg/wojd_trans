import json,pathlib,sys,tempfile,unittest
ROOT=pathlib.Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'scripts'))
from compile_locres_bindings import load_bindings,compile_bindings
from locres_verify import read_bytes,Invalid

class BindingTests(unittest.TestCase):
    def test_crc_identity_newline_and_spacing_survive_without_source_inference(self):
        original={('Tên','甲'):(0xffffffff,'  Tiếng Việt\nĐúng\r\nDòng\rCuối  '),('','empty'):(0,''),('Tên','乙'):(123,'Tương truyền')}
        data=compile_bindings(original)
        self.assertEqual(read_bytes(data),original)
        self.assertEqual(compile_bindings(dict(reversed(list(original.items())))),data)
        damaged=bytearray(data);damaged[-1]^=1
        with self.assertRaises(Invalid):read_bytes(bytes(damaged))

    def test_duplicate_and_invalid_bindings_rejected(self):
        row=dict(namespace='',key='id',source_crc=1,target='trtr')
        with tempfile.TemporaryDirectory(dir=ROOT/'work') as directory:
            path=pathlib.Path(directory)/'bindings.ndjson'
            def put(rows):path.write_bytes(('\n'.join(json.dumps(r) for r in rows)+'\n').encode())
            put([row,row])
            with self.assertRaisesRegex(ValueError,'Duplicate'):load_bindings(path)
            for change in [dict(source_crc=True),dict(source_crc=-1),dict(key=''),dict(target='bad\0text'),dict(extra='unexpected')]:
                put([dict(row,**change)])
                with self.assertRaises(ValueError):load_bindings(path)
            put([row]);self.assertEqual(load_bindings(path),{('','id'):(1,'trtr')})
            # Cooking preserves approved runtime text. Lexical review is separate.

if __name__=='__main__':unittest.main()
