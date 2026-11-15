# Como iniciar no Windows

## Primeira vez

1. Extraia todo o ZIP para uma pasta normal.
2. Execute `PREPARAR-WINDOWS.bat`.
3. Se o Python 3.12 (64 bits) não estiver instalado, o preparador tentará instalá-lo pelo Gerenciador de Pacotes do Windows (`winget`).
4. O preparador cria `.venv` e instala as dependências isoladamente.
5. Depois execute `INICIAR.bat`.

## Criar o executável

Depois que `PREPARAR-WINDOWS.bat` concluir com sucesso, execute `CRIAR-EXECUTAVEL.bat`.

O build será colocado em `dist`. O modo `onedir` é usado quando não existe configuração `.spec`, pois costuma ser mais confiável para aplicações grandes com áudio, Qt e bibliotecas nativas.

## Importante

Este ZIP contém o projeto preparado para Windows. O arquivo `.exe` precisa ser compilado em Windows para incorporar corretamente DLLs e dependências específicas do sistema. Um executável Windows não deve ser considerado validado apenas por ter sido produzido em Linux.

Se algo falhar, a janela do `.bat` permanece aberta mostrando o erro em vez de desaparecer.
