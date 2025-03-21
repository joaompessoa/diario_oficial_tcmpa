from documents.diario import DiarioOficial
from documents.acordao import Acordao

if __name__ == "__main__":
    # Create an instance of the DiarioOficial class
    # diario = DiarioOficial()
    # print(diario)

    acordao = Acordao(diario=DiarioOficial(dia=19, mes=3, ano=2025))
    print(acordao)
    print(acordao.diario.numero_diario)
    
# TODO
# Add a simetrie entre a classe DiarioOficial e as outras classes baseadas em documento
# A classe acordao por exemplo, pode iniciar DiarioOficial caso ela nao tenha sido iniciada
# TODO criar um front end


   
    