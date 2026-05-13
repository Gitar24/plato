const button = document.querySelector("#button");
button.addEventListener("click", () => {
    const codigo = document.querySelector("#codigo");
    const resposta = document.querySelector("#resposta");
    if (codigo.value === "" || codigo.value.trim() === "") {
        resposta.innerHTML = `nao foi encontrado nenhum texto no campo`;
        return;
    }
    resposta.innerHTML = `[ Plato analisando... ]`;
    setTimeout(() => {resposta.innerHTML = `seu codigo foi recebido com sucesso`;}, 1000) 
});