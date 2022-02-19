
from fastapi import FastAPI, Request, File, Form, UploadFile, status
from fastapi.responses import HTMLResponse, RedirectResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from main import Aplikasi
import datetime as dt


app = FastAPI()
templates = Jinja2Templates(directory='templates')
app.mount("/static", StaticFiles(directory="static"), name="static")

apl = Aplikasi()

@app.get("/", response_class=HTMLResponse)
def home(request: Request, save: int = 'None', saved: str = 'None', tgl: str = 'None'):
    data = apl.get_db(3)

    if tgl != 'None':
        data = list(filter(lambda row: row[0] == tgl, data))

    return templates.TemplateResponse("index.html", {"request": request, "data": data, "save": save, "saved": saved, "tgl": tgl})

@app.get("/{jml}", response_class=HTMLResponse)
def jml(request: Request, jml: int = None, save: int = 'None', saved: str = 'None', tgl: str = 'None'):
    data = apl.get_db(jml-100)

    if tgl != 'None':
        data = apl.get_db(3)
        data = list(filter(lambda row: row[0] == tgl, data))[:jml]

    return templates.TemplateResponse("index.html", {"request": request, "data": data, "jml": jml, "save": save, "saved": saved, "tgl": tgl})

@app.post('/jml')
def go(jml = Form(...), tgl = Form(...)):
    if tgl is None or tgl == 'None':
        return RedirectResponse(f'/{jml}', status_code=status.HTTP_302_FOUND)
    else:
        return RedirectResponse(f'/{jml}?tgl={tgl}', status_code=status.HTTP_302_FOUND)

@app.post('/inp_tgl/{jml}')
def input_tgl(jml: int = None, inp_tgl: dt.date = Form(...), tgl: str = Form(...)):
    date_str = dt.datetime.strftime(inp_tgl, '%d %B %Y')
    url = apl.create_url(date_str)
    data = apl.scrape_harga(url)
    saved = apl.save_db(data, inp_tgl)

    if jml == 0:
        jml = ''
    else:
        jml /= 10
        jml = int(jml)

    if tgl and tgl != 'None':
        return RedirectResponse(f'/{jml}?save={saved}&tgl={tgl}', status_code=status.HTTP_302_FOUND)
    else:
        return RedirectResponse(f'/{jml}?save={saved}', status_code=status.HTTP_302_FOUND)

@app.post('/upload/{jml}')
def upload(jml: int = None, file: UploadFile = File(...), tgl: str = Form(...)):
    saved = apl.csv_to_db(file.file.readlines())
    if jml == 0:
        jml = ''
    else:
        jml /= 10
        jml = int(jml)

    if tgl and tgl != 'None':
        return RedirectResponse(f'/{jml}?save={saved}&tgl={tgl}', status_code=status.HTTP_302_FOUND)
    else:
        return RedirectResponse(f'/{jml}?save={saved}', status_code=status.HTTP_302_FOUND)

