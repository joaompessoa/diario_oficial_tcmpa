from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional
import os
from datetime import datetime
import uvicorn


from documents.diario import DiarioOficial
from exceptions.diario_exceptions import DiarioNaoExiste

app = FastAPI(
    title="API de Consulta de Diário Oficial TCMPA",
    description="API para consulta de Diários Oficiais do Tribunal de Contas dos Municípios do Estado do Pará",
    version="1.0.0"
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


app.mount("/static", StaticFiles(directory="static"), name="static")

class DiarioResponse(BaseModel):
    encontrado: bool
    publicacao: str
    pdf_url: Optional[str] = None
    numero_diario: Optional[str] = None
    mensagem: Optional[str] = None


@app.get("/", include_in_schema=False)
async def root():
    """
    Serve a página HTML principal.
    """
    return FileResponse("static/index.html")


@app.get("/api/diario", response_model=DiarioResponse)
async def consultar_diario(
    dia: int = Query(..., description="Dia do mês (1-31)"),
    mes: int = Query(..., description="Mês (1-12)"),
    ano: int = Query(..., description="Ano (ex: 2024)")
) -> DiarioResponse:
    """
    Consulta o Diário Oficial do TCMPA para a data especificada.
    
    Parameters:
    - dia: Dia do mês (1-31)
    - mes: Mês (1-12)
    - ano: Ano (ex: 2024)
    
    Returns:
    - Informações sobre o Diário Oficial encontrado
    """
    try:
        # Validar data (não pode ser no futuro)
        data_consulta = datetime(ano, mes, dia)
        if data_consulta > datetime.today():
            raise HTTPException(
                status_code=400, 
                detail=f"A data {dia}/{mes}/{ano} é futura e não pode ser consultada."
            )
        
        # Tentar obter o diário oficial
        diario = DiarioOficial(dia=dia, mes=mes, ano=ano)
        
        # Se chegou aqui, o diário foi encontrado
        return DiarioResponse(
            encontrado=True,
            publicacao=f"{dia}/{mes}/{ano}",
            pdf_url=f"/api/diario/download?dia={dia}&mes={mes}&ano={ano}",
            numero_diario=diario.numero_diario,
            mensagem="Diário Oficial encontrado com sucesso."
        )
        
    except DiarioNaoExiste as e:
        # Diário não existe ou não foi encontrado
        return DiarioResponse(
            encontrado=False,
            publicacao=f"{dia}/{mes}/{ano}",
            mensagem=str(e)
        )
        
    except Exception as e:
        # Outros erros
        raise HTTPException(
            status_code=500,
            detail=f"Erro ao consultar o Diário Oficial: {str(e)}"
        )

@app.get("/api/diario/download")
async def download_diario(
    dia: int = Query(..., description="Dia do mês (1-31)"),
    mes: int = Query(..., description="Mês (1-12)"),
    ano: int = Query(..., description="Ano (ex: 2024)")
) -> FileResponse:
    """
    Faz o download do PDF do Diário Oficial do TCMPA para a data especificada.
    
    Parameters:
    - dia: Dia do mês (1-31)
    - mes: Mês (1-12)
    - ano: Ano (ex: 2024)
    
    Returns:
    - Arquivo PDF do Diário Oficial
    """
    try:
        # Tentar obter o diário oficial
        diario = DiarioOficial(dia=dia, mes=mes, ano=ano)
        
        # Verificar se o arquivo PDF existe
        if os.path.exists(diario.local_path) and os.path.isfile(diario.local_path):
            return FileResponse(
                path=diario.local_path,
                media_type="application/pdf",
                filename=f"diario_tcmpa_{ano}{mes:02d}{dia:02d}.pdf"
            )
        else:
            raise HTTPException(
                status_code=404,
                detail=f"Arquivo PDF não encontrado para a data {dia}/{mes}/{ano}."
            )
            
    except DiarioNaoExiste as e:
        raise HTTPException(
            status_code=404,
            detail=str(e)
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Erro ao fazer download do Diário Oficial: {str(e)}"
        )

@app.get("/api/status")
async def status():
    """
    Verifica o status da API
    """
    return {"status": "online", "timestamp": datetime.now().isoformat()}

if __name__ == "__main__":
    uvicorn.run("api:app", host="0.0.0.0", port=8000, reload=True)
