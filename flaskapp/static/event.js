let typeOp = document.getElementById("formOperation")
let typeWs = document.getElementById("formWorkshop")
let typeEv = document.getElementById("formEvent")

/**
 * Makes all forms hidden except for one.
 * @param {HTMLElement} str That one non-hidden form.
 */
function formVis(type) {
    const forms = document.getElementsByTagName("form")
    /* Determine visibility */
    for (let i = 0; i < forms.length; i++)
        forms[i].hidden = (type === forms[i] ? false : true)
}

formVis(typeOp) // Run on start. Op is default

eventType = document.getElementsByName("eventType")[0]
eventType.selectedIndex = 0 // Maybe doesn't work. Intent is trying to reset select on refresh etc.
eventType.addEventListener("change", () => {
    if (eventType.value == "Operation") {
        formVis(typeOp)

    } else if (eventType.value == "Workshop") {
        formVis(typeWs)

    } else {  // Event
        formVis(typeEv)
    }
})
