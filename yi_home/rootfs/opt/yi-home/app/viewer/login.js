const form=document.querySelector('#login-form'),error=document.querySelector('#login-error');
form.addEventListener('submit',async event=>{event.preventDefault();const button=form.querySelector('button');button.disabled=true;error.hidden=true;
 try{const response=await fetch('/auth/login',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({password:form.password.value})});
  if(!response.ok)throw new Error(await response.text());form.reset();location.replace('/');
 }catch(e){error.textContent=e.message||'Unable to sign in. Please try again.';error.hidden=false;button.disabled=false}
});
