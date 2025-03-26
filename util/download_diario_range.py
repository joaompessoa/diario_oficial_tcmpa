from documents.diario import DiarioOficial
from datetime import datetime
from exceptions.diario_exceptions import DiarioNaoExiste
from calendar import monthrange
from util.logger_config import logger
from time import sleep

class DiarioRange:
    def __init__(self, mes: int  = None, ano: int = None):
        self.mes: int = mes or datetime.today().month
        self.ano: int = ano or datetime.today().year
    
    def get_diario_month(self, mes: int = None):
        if not mes:
            mes = self.mes
        _,dias_no_mes = monthrange(self.ano, mes)
        local_paths = []
        for dia in range(1,dias_no_mes):
            try:
                diario = DiarioOficial(
                        dia=dia,
                        mes=mes,
                        ano=self.ano
                    )
                local_paths.append(diario.local_path)
            except DiarioNaoExiste:
                logger.warning(f"Diario nao existe para {dia}/{self.mes}/{self.ano}")
                continue
        return local_paths
    
    def month_pt(self, mes: int) -> str:
        match mes:
            case 1:
                return 'janeiro'
            case 2:
                return 'fevereiro'
            case 3:
                return 'março'
            case 4:
                return 'abril'
            case 5:
                return 'maio'
            case 6:
                return 'junho'
            case 7:
                return 'julho'
            case 8:
                return 'agosto'
            case 9:
                return 'setembro'
            case 10:
                return 'outubro'
            case 11:
                return 'novembro'
            case 12:
                return 'dezembro'
            case _:
                raise ValueError("Número de mês inválido")
            
    def get_diario_ano(self, ano: int = None):
        if not ano:
            ano = self.ano
        meses = range(1,13)
        current_month = datetime.today().month
        diarios_ano = []
        for mes in meses:
            if mes > current_month:
                logger.warning(f'{mes} e maior que o mes atual {current_month}, logo no futuro, entao quebramos o loop')
                break
            mes_pt = self.month_pt(mes)
            logger.debug(f'Comecando a busca para o mes: {mes_pt} de {ano}')
            diarios_mes = self.get_diario_month(mes=mes)
            entry = {mes_pt: diarios_mes}
            logger.debug(f'Entrada do {mes_pt} no {ano} \n\n {entry}')
            diarios_ano.append(entry)
            sleep(5)
        return diarios_ano
    

def obter_diarios_mes(mes: int | str | None, ano: int | str | None) -> list:
    if not isinstance(mes, int) or not isinstance(ano, int):
        try:
            ano = int(ano)
            mes = int(mes)
        except TypeError:
            logger.error(f"Valores de ano {ano} ou mes {mes} sao invalidos, use numeros inteiros")
   
    diarios = DiarioRange(mes, ano)
    diarios_no_mes = diarios.get_diario_month()
    return diarios_no_mes

def obter_diarios_ano(ano: int) -> list[dict]:
    diarios = DiarioRange(ano=ano)
    diarios_no_ano = diarios.get_diario_ano()
    return diarios_no_ano