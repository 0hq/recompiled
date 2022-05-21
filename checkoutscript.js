/* Fetch prices and update the form */
fetch("/config")
  .then(r => r.json())
  .then(({basicPrice}) => {
    const basicPriceInput = document.querySelector('#basicPrice');
    basicPriceInput.value = "price_1Kx1ECEDdGyhVvwd5Q0BTcOX";
    // const proPriceInput = document.querySelector('#proPrice');
    // proPriceInput.value = proPrice;
  })
