from flask import Flask, request, jsonify, send_file, abort, Response
from flask_cors import CORS
from pydantic import BaseModel

from typing import Optional
import os
from datetime import datetime
from pathlib import Path

from documents.diario import DiarioOficial, DataDiario
from exceptions.diario_exceptions import DiarioNaoExiste, DataFutura
from util.logger_config import setup_logger


logger = setup_logger()

app = Flask(__name__, static_folder="static", static_url_path="/static")
CORS(app)


class DiarioResponse(BaseModel):
    encontrado: bool
    publicacao: str
    pdf_url: Optional[str] = None
    numero_diario: Optional[str] = None
    mensagem: Optional[str] = None


@app.route("/")
def root() -> Response:
    """
    Serve a página HTML principal.
    """
    return send_file("static/index.html")


@app.route("/api/status", methods=["GET"])
def status() -> Response:
    """
    Verifica o status da API
    """
    return jsonify({"status": "online", "timestamp": datetime.now().isoformat()})


@app.route("/api/diario", methods=["GET"])
def consultar_diario() -> Response:
    """
    Consulta o Diário Oficial do TCMPA para a data especificada.

    Query Parameters:
    - dia: Dia do mês (1-31) ou 'hoje' para o dia atual
    - mes: Mês (1-12), opcional (default: mês atual)
    - ano: Ano (ex: 2024), opcional (default: ano atual)

    Returns:
    - Informações sobre o Diário Oficial encontrado
    """
    try:
        hoje = datetime.today()

        # Verificar se o parâmetro 'dia' é 'hoje'
        dia_param = request.args.get("dia")
        if dia_param == "hoje":
            dia = hoje.day
            mes = hoje.month
            ano = hoje.year
        else:
            # Extrair parâmetros com defaults
            dia = request.args.get("dia")
            mes = request.args.get("mes", default=str(hoje.month))
            ano = request.args.get("ano", default=str(hoje.year))

        # Verificar se dia foi fornecido
        if dia is None and dia_param != "hoje":
            abort(400, description="O parâmetro 'dia' é obrigatório.")

        # Usar a classe DataDiario para validação
        try:
            data_consulta = DataDiario(dia=dia, mes=mes, ano=ano)
        except DataFutura as e:
            response = DiarioResponse(
                encontrado=False, publicacao=f"{dia}/{mes}/{ano}", mensagem=str(e)
            )
            return jsonify(response.model_dump())
        except ValueError as e:
            abort(400, description=f"Erro na validação da data: {str(e)}")

        # Tentar obter o diário oficial
        diario = DiarioOficial(**data_consulta.model_dump())

        # Se chegou aqui, o diário foi encontrado
        response = DiarioResponse(
            encontrado=True,
            publicacao=f"{data_consulta.dia}/{data_consulta.mes}/{data_consulta.ano}",
            pdf_url=f"/api/diario/download?dia={data_consulta.dia}&mes={data_consulta.mes}&ano={data_consulta.ano}",
            numero_diario=diario.numero_diario,
            mensagem="Diário Oficial encontrado com sucesso.",
        )

        return jsonify(response.model_dump())

    except DataFutura as e:
        # Data futura não pode ser consultada
        response = DiarioResponse(
            encontrado=False, publicacao=f"{dia}/{mes}/{ano}", mensagem=str(e)
        )
        return jsonify(response.model_dump())
    except DiarioNaoExiste as e:
        # Diário não existe ou não foi encontrado
        response = DiarioResponse(
            encontrado=False, publicacao=f"{dia}/{mes}/{ano}", mensagem=str(e)
        )
        return jsonify(response.model_dump())
    except ValueError:
        # Erro de conversão de data
        abort(
            400,
            description="Parâmetros dia, mes e ano devem ser inteiros e válidos.",
        )
    except Exception as e:
        # Outros erros
        logger.error(f"Erro ao consultar o Diário Oficial: {str(e)}")
        abort(500, description=f"Erro ao consultar o Diário Oficial: {str(e)}")


@app.route("/api/diario/acordaos", methods=["GET"])
def listar_acordaos() -> Response:
    """
    Lista os Acórdãos do Diário Oficial do TCMPA para a data especificada.

    Query Parameters:
    - dia: Dia do mês (1-31) ou 'hoje' para o dia atual
    - mes: Mês (1-12), opcional (default: mês atual)
    - ano: Ano (ex: 2024), opcional (default: ano atual)

    Returns:
    - Lista de Acórdãos encontrados no Diário Oficial
    """
    try:
        hoje = datetime.today()

        # Verificar se o parâmetro 'dia' é 'hoje'
        dia_param = request.args.get("dia")
        if dia_param == "hoje":
            dia = hoje.day
            mes = hoje.month
            ano = hoje.year
        else:
            # Extrair parâmetros com defaults
            dia = request.args.get("dia")
            mes = request.args.get("mes", default=str(hoje.month))
            ano = request.args.get("ano", default=str(hoje.year))

        # Verificar se dia foi fornecido
        if dia is None and dia_param != "hoje":
            abort(400, description="O parâmetro 'dia' é obrigatório.")

        # Usar a classe DataDiario para validação
        try:
            data_consulta = DataDiario(dia=dia, mes=mes, ano=ano)
        except DataFutura as e:
            return jsonify({"status": "error", "mensagem": str(e), "acordaos": []})
        except ValueError as e:
            abort(400, description=f"Erro na validação da data: {str(e)}")

        # Tentar obter o diário oficial
        diario = DiarioOficial(**data_consulta.model_dump())

        # Obter os acórdãos do diário
        from documents.acordao import Acordao

        acordaos = Acordao(diario=diario)

        # Converter para formato JSON
        resultado = []
        for doc in acordaos.documentos:
            # Converta cada DocumentoDiarioOficial para dict, excluindo texto_original que pode ser muito grande
            doc_dict = doc.model_dump()
            if "texto_original" in doc_dict:
                del doc_dict["texto_original"]
            resultado.append(doc_dict)

        return jsonify(
            {
                "status": "success",
                "mensagem": f"Encontrados {len(resultado)} acórdãos",
                "acordaos": resultado,
            }
        )

    except DiarioNaoExiste as e:
        logger.error(f"Diário não existe: {str(e)}")
        return jsonify({"status": "error", "mensagem": str(e), "acordaos": []})
    except Exception as e:
        logger.error(f"Erro ao listar acórdãos: {str(e)}")
        return jsonify(
            {
                "status": "error",
                "mensagem": f"Erro ao listar acórdãos: {str(e)}",
                "acordaos": [],
            }
        )


@app.route("/api/diario/resolucoes", methods=["GET"])
def listar_resolucoes() -> Response:
    """
    Lista as Resoluções do Diário Oficial do TCMPA para a data especificada.

    Query Parameters:
    - dia: Dia do mês (1-31) ou 'hoje' para o dia atual
    - mes: Mês (1-12), opcional (default: mês atual)
    - ano: Ano (ex: 2024), opcional (default: ano atual)

    Returns:
    - Lista de Resoluções encontradas no Diário Oficial
    """
    try:
        hoje = datetime.today()

        # Verificar se o parâmetro 'dia' é 'hoje'
        dia_param = request.args.get("dia")
        if dia_param == "hoje":
            dia = hoje.day
            mes = hoje.month
            ano = hoje.year
        else:
            # Extrair parâmetros com defaults
            dia = request.args.get("dia")
            mes = request.args.get("mes", default=str(hoje.month))
            ano = request.args.get("ano", default=str(hoje.year))

        # Verificar se dia foi fornecido
        if dia is None and dia_param != "hoje":
            abort(400, description="O parâmetro 'dia' é obrigatório.")

        # Usar a classe DataDiario para validação
        try:
            data_consulta = DataDiario(dia=dia, mes=mes, ano=ano)
        except DataFutura as e:
            return jsonify({"status": "error", "mensagem": str(e), "resolucoes": []})
        except ValueError as e:
            abort(400, description=f"Erro na validação da data: {str(e)}")

        # Tentar obter o diário oficial
        diario = DiarioOficial(**data_consulta.model_dump())

        # Obter as resoluções do diário
        from documents.resolucao import Resolucao

        resolucoes = Resolucao(diario=diario)

        # Converter para formato JSON
        resultado = []
        for doc in resolucoes.documentos:
            # Converta cada DocumentoDiarioOficial para dict, excluindo texto_original que pode ser muito grande
            doc_dict = doc.model_dump()
            if "texto_original" in doc_dict:
                del doc_dict["texto_original"]
            resultado.append(doc_dict)

        return jsonify(
            {
                "status": "success",
                "mensagem": f"Encontradas {len(resultado)} resoluções",
                "resolucoes": resultado,
            }
        )

    except DiarioNaoExiste as e:
        logger.error(f"Diário não existe: {str(e)}")
        return jsonify({"status": "error", "mensagem": str(e), "resolucoes": []})
    except Exception as e:
        logger.error(f"Erro ao listar resoluções: {str(e)}")
        return jsonify(
            {
                "status": "error",
                "mensagem": f"Erro ao listar resoluções: {str(e)}",
                "resolucoes": [],
            }
        )


@app.route("/api/diario/download")
def download_diario() -> Response:
    """
    Faz o download do PDF do Diário Oficial do TCMPA para a data especificada.

    Query Parameters:
    - dia: Dia do mês (1-31) ou 'hoje' para o dia atual
    - mes: Mês (1-12), opcional (default: mês atual)
    - ano: Ano (ex: 2024), opcional (default: ano atual)

    Returns:
    - Arquivo PDF do Diário Oficial
    """
    try:
        hoje = datetime.today()

        # Verificar se o parâmetro 'dia' é 'hoje'
        dia_param = request.args.get("dia")
        if dia_param == "hoje":
            dia = hoje.day
            mes = hoje.month
            ano = hoje.year
        else:
            # Extrair parâmetros com defaults
            dia = request.args.get("dia")
            mes = request.args.get("mes", default=str(hoje.month))
            ano = request.args.get("ano", default=str(hoje.year))

        # Verificar se dia foi fornecido
        if dia is None and dia_param != "hoje":
            abort(400, description="O parâmetro 'dia' é obrigatório.")

        # Usar a classe DataDiario para validação
        try:
            data_consulta = DataDiario(dia=dia, mes=mes, ano=ano)
        except DataFutura as e:
            abort(400, description=str(e))
        except ValueError as e:
            abort(400, description=f"Erro na validação da data: {str(e)}")

        # Tentar obter o diário oficial
        diario = DiarioOficial(**data_consulta.model_dump())

        # Verificar se o arquivo PDF existe
        if os.path.exists(diario.local_path) and os.path.isfile(diario.local_path):
            logger.success(
                f"Arquivo PDF baixado para: {diario.local_path}"
            )
            return send_file(
                diario.local_path,
                mimetype="application/pdf",
                download_name=f"diario_tcmpa_{data_consulta.ano}{data_consulta.mes:02d}{data_consulta.dia:02d}.pdf",
                as_attachment=True,
            )
        else:
            message = f"Arquivo PDF não encontrado para a data {data_consulta.dia}/{data_consulta.mes}/{data_consulta.ano}.",

            logger.error(
                message
            )

            abort(
                404,
                description=message
            )

    except DiarioNaoExiste as e:
        logger.error(
            f"Diário não existe ou não foi encontrado: {str(e)}"
        )
        abort(404, description=str(e))

    except Exception as e:
        message = f"Erro ao fazer download do Diário Oficial: {str(e)}"
        logger.error(message)
        abort(500, description=message)


@app.route("/api/diario/logs")
def get_logs() -> Response:
    """
    Retorna os logs da API.

    Query Parameters:
    - lines: Número de linhas a retornar (padrão: 100)
    - level: Nível mínimo de log (DEBUG (padrao), INFO, WARNING, ERROR, CRITICAL)

    Returns:
    - JSON com logs da aplicação
    """
    try:
        # Obter parâmetros opcionais
        lines = request.args.get("lines", default=100, type=int)
        level = request.args.get("level", default="DEBUG").upper()

        # Validar o nível de log
        valid_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
        if level not in valid_levels:
            abort(
                400,
                description=f"Nível de log inválido. Use um dos seguintes: {', '.join(valid_levels)}",
            )

        # Caminho para o arquivo de log
        base_dir = Path(__file__).parent
        log_dir = base_dir / "logs"
        log_file = log_dir / "diario.log"

        if not log_file.exists():
            return jsonify(
                {
                    "status": "error",
                    "message": "Arquivo de log não encontrado",
                    "logs": [],
                }
            )

        # Ler as últimas linhas do arquivo de log
        logs = []
        level_priorities = {
            "DEBUG": 0,
            "INFO": 1,
            "WARNING": 2,
            "ERROR": 3,
            "CRITICAL": 4,
        }
        min_priority = level_priorities.get(level, 0)

        with open(log_file, "r", encoding="utf-8") as file:
            all_lines = file.readlines()
            # Filtrar por nível e limitar o número de linhas
            filtered_lines = []
            for line in reversed(
                all_lines
            ):  # Ler de trás para frente para pegar as mais recentes
                line_parts = line.strip().split("|")
                if len(line_parts) >= 2:
                    log_level = line_parts[1].strip()
                    log_priority = level_priorities.get(log_level, 0)
                    if log_priority >= min_priority:
                        filtered_lines.append(line.strip())
                        if len(filtered_lines) >= lines:
                            break

            # Inverter novamente para ordem cronológica
            logs = list(reversed(filtered_lines))

        return jsonify(
            {"status": "success", "count": len(logs), "level": level, "logs": logs}
        )

    except Exception as e:
        logger.error(f"Erro ao obter logs: {str(e)}")
        abort(500, description=f"Erro ao obter logs: {str(e)}")


@app.route("/docs")
def api_docs()-> Response:
    """
    Serve the API documentation page.
    """
    return send_file("static/docs.html")


@app.errorhandler(400)
def bad_request(error):
    return jsonify({"error": error.description}), 400


@app.errorhandler(404)
def not_found(error):
    return jsonify({"error": error.description}), 404


@app.errorhandler(500)
def server_error(error):
    return jsonify({"error": error.description}), 500


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000, debug=True)
