let elmButton = document.querySelector("#submit");
const queryString = window.location.search;
console.log(queryString);
const urlParams = new URLSearchParams(queryString);

if (elmButton) {
  console.log({
    'writer_email': urlParams.get('writer_email'),
    'secret_code': urlParams.get('secret_code')
  })
  elmButton.addEventListener(
    "click",
    e => {
      elmButton.setAttribute("disabled", "disabled");
      elmButton.textContent = "Opening...";

      fetch("/onboard-user", {
        method: "POST",
        headers: {
          "Content-Type": "application/json"
        },
        data: JSON.stringify({
          'writer_email': urlParams.get('writer_email'),
          'secret_code': urlParams.get('secret_code')
        }),
        body: JSON.stringify({
          'writer_email': urlParams.get('writer_email'),
          'secret_code': urlParams.get('secret_code')
        })
      })
        .then(response => response.json())
        .then(data => {
          if (data.url) {
            window.location = data.url;
          } else {
            elmButton.removeAttribute("disabled");
            elmButton.textContent = "<Something went wrong>";
            console.log("data", data);
          }
        });
    },
    false
  );
}
