import mimetypes
import os
import tempfile
import magic
import requests
from .parsers.text_parser import textParser
from .parsers.csv_parser import csvParser
from .parsers.web_parser import webParser
from .parsers.pdf_parser import pdfParser
from .parsers.docx_parser import docxParser
from .parsers.excelParser import excelParser
from .chunker import chunker

class Reader:
    def __init__(self, source):

        #initial input, either a url or a file
        self.source = source
        self.isURL = self.is_url()
        #if its a url, download the file and save it to a temporary location, otherwise use the input as the file path

        if self.isURL:
            self.file = self.download_url()
        else:
            if not os.path.exists(self.source):
                raise FileNotFoundError(f"File not found: {self.source}")
            self.file = self.source

        self.fileType = self.getFileType()
        self.parsed_data = self.parse()
        self.chunks = chunker(self.parsed_data)
        




    def is_url(self):
        #is it a url? check if it starts with http:// or https://
        return self.source.startswith("http://") or self.source.startswith("https://")
    
    def download_url(self):
        response = requests.get(self.source)
        response.raise_for_status()  # fail early on 4xx/5xx

        # get extension from Content-Type header
        content_type = response.headers.get("Content-Type", "")
        extension = mimetypes.guess_extension(content_type.split(";")[0]) or ".bin"

        # write to a temp file that persists until you're done with it
        tmp = tempfile.NamedTemporaryFile(suffix=extension, delete=False)
        tmp.write(response.content)
        tmp.close()

        return tmp.name

    def getFileType(self):
        mime = magic.from_file(self.file, mime=True)
        return mime
    
    def parse(self):
        if self.fileType in ["text/plain"]:
            return textParser(self.file)
        elif self.fileType in ["text/csv"]:
            return csvParser(self.file)
        elif self.fileType in ["text/html"]:
            return webParser(self.file)
        elif self.fileType in ["application/pdf"]:
            return pdfParser(self.file)
        elif self.fileType in ["application/vnd.openxmlformats-officedocument.wordprocessingml.document"]:
            return docxParser(self.file)
        elif self.fileType in ["application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", "application/vnd.ms-excel"]:
            return excelParser(self.file)
        else:
            raise ValueError(f"Unsupported file type: {self.fileType}")