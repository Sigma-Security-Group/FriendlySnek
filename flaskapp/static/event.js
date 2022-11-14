// Fetch all forms
let typeOp = document.getElementById("formOperation")
let typeWs = document.getElementById("formWorkshop")
let typeEv = document.getElementById("formEvent")
let types = [typeOp, typeWs, typeEv]

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


// Set textarea values
const textareaIdentifier = "JS_CHANGE_VALUE"
let textareas = document.getElementsByTagName("textarea")
for (let i = 0; i < textareas.length; i++) {
    if (textareas[i].placeholder.startsWith(textareaIdentifier)) {
        textareas[i].placeholder = textareas[i].placeholder.replace(textareaIdentifier, "")
        textareas[i].value = textareas[i].placeholder
    }
}

// Event type
eventType = document.getElementsByName("eventType")[0]
formVis(types[eventType.selectedIndex])
eventType.addEventListener("change", () => {
    if (eventType.value == "Operation") {
        formVis(typeOp)

    } else if (eventType.value == "Workshop") {
        formVis(typeWs)

    } else {  // Event
        formVis(typeEv)
    }
})
