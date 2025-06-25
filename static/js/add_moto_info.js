document.addEventListener('DOMContentLoaded', function() {
    // Обработчики для кнопок отмены
    const cancelBtn1 = document.getElementById('cancel-btn-step1');
    const cancelBtn2 = document.getElementById('cancel-btn-step2');
    const cancelBtn3 = document.getElementById('cancel-btn-step3');
    const cancelBtn4 = document.getElementById('cancel-btn-step4');
    
    if (cancelBtn1) {
        cancelBtn1.addEventListener('click', function() {
            window.location.href = "/index";
        });
    }
    
    if (cancelBtn2) {
        cancelBtn2.addEventListener('click', function() {
            window.location.href = "/index";
        });
    }
    
    if (cancelBtn3) {
        cancelBtn3.addEventListener('click', function() {
            window.location.href = "/index";
        });
    }

    if (cancelBtn4) {
        cancelBtn4.addEventListener('click', function() {
            window.location.href = "/index";
        });
    }
    
    // Предотвращаем отправку формы по нажатию Enter
    document.getElementById('moto-form').addEventListener('keypress', function(e) {
        if (e.key === 'Enter') {
            e.preventDefault();
        }
    });
});


// Обработка загрузки и замены фото
const photoUpload = document.getElementById('photo-upload');
const photoInput = document.getElementById('photo-input');
const previewPhoto = document.getElementById('preview-photo');
const replacePhotoContainer = document.getElementById('replace-photo-container');
const replacePhotoBtn = document.getElementById('replace-photo-btn');

photoUpload.addEventListener('click', () => photoInput.click());

photoInput.addEventListener('change', function(e) {
    handlePhotoSelection(e.target.files[0]);
});

replacePhotoBtn.addEventListener('click', function() {
    photoInput.value = '';
    previewPhoto.style.display = 'none';
    photoUpload.style.display = 'block';
    replacePhotoContainer.style.display = 'none';
    document.getElementById('confirm-photo').textContent = 'Не загружено';
});

function handlePhotoSelection(file) {
    if (file) {
        if (file.size > 2 * 1024 * 1024) {
            alert('Файл слишком большой (больше 2МБ)');
            photoInput.value = '';
            return;
        }

        const reader = new FileReader();
        reader.onload = function(event) {
            previewPhoto.src = event.target.result;
            previewPhoto.style.display = 'block';
            photoUpload.style.display = 'none';
            replacePhotoContainer.style.display = 'block';
            document.getElementById('confirm-photo').textContent = 'Загружено';
        };
        reader.readAsDataURL(file);
    }
}

// Навигация по шагам
let currentStep = 1;

function updateStepIndicator(step) {
    document.querySelectorAll('.step').forEach((el, index) => {
        if (index + 1 <= step) {
            el.classList.add('active');
        } else {
            el.classList.remove('active');
        }
    });
}

function goToStep(step) {
    document.querySelectorAll('.step-form').forEach(form => {
        form.classList.remove('active', 'leaving');
    });

    const targetForm = document.getElementById(`step-${step}`);
    targetForm.classList.add('active');
    updateStepIndicator(step);
    currentStep = step;

    if (step === 3) {
        updateConfirmationData();
    }
}

function nextStep(current, next) {
    if (current === 1 && !validateStep1()) return;
    if (current === 2 && !validateStep2()) return;

    const currentForm = document.getElementById(`step-${current}`);
    currentForm.classList.add('leaving');

    setTimeout(() => {
        goToStep(next);
    }, 300);
}

function prevStep(current, prev) {
    const currentForm = document.getElementById(`step-${current}`);
    currentForm.classList.add('leaving');

    setTimeout(() => {
        goToStep(prev);
    }, 300);
}

function validateStep1() {
    const model = document.getElementById('model').value;
    if (!model.trim()) {
        alert('Пожалуйста, укажите модель мотоцикла');
        return false;
    }
    return true;
}

function validateStep2() {
    const year = document.getElementById('year').value;
    const mileage = document.getElementById('mileage').value;
    const engine = document.getElementById('engine').value;
    const type = document.getElementById('type').value;
    const drive_type = document.getElementById('drive_type').value;

    if (!year || !mileage || !engine || !type || !drive_type) {
        alert('Пожалуйста, заполните все поля');
        return false;
    }

    const currentYear = new Date().getFullYear();
    if (year < 1900 || year > currentYear + 1) {
        alert(`Пожалуйста, укажите корректный год выпуска (1900-${currentYear + 1})`);
        return false;
    }

    if (mileage < 0) {
        alert('Пробег не может быть отрицательным');
        return false;
    }

    if (engine < 50) {
        alert('Объем двигателя должен быть не менее 50 см³');
        return false;
    }

    return true;
}

function updateConfirmationData() {
    document.getElementById('confirm-model').textContent = document.getElementById('model').value;
    document.getElementById('confirm-year').textContent = document.getElementById('year').value;
    document.getElementById('confirm-mileage').textContent = document.getElementById('mileage').value + ' км';
    document.getElementById('confirm-engine').textContent = document.getElementById('engine').value + ' см³';

    const typeSelect = document.getElementById('type');
    document.getElementById('confirm-type').textContent = typeSelect.options[typeSelect.selectedIndex].text;

    const driveTypeSelect = document.getElementById('drive_type');
    document.getElementById('confirm-drive-type').textContent = driveTypeSelect.options[driveTypeSelect.selectedIndex].text;

    if (previewPhoto.style.display === 'block') {
        document.getElementById('confirm-photo').textContent = 'Загружено';
    } else {
        document.getElementById('confirm-photo').textContent = 'Не загружено';
    }
}

// Обработчик подтверждения формы
document.getElementById('confirm-btn').addEventListener('click', function(e) {
    e.preventDefault();
    submitForm();
});

// Обработчики кнопок next/prev — отключаем перезагрузку
document.querySelectorAll('[onclick^="nextStep"], [onclick^="prevStep"]').forEach(btn => {
    btn.addEventListener('click', function(e) {
        e.preventDefault();
    });
});

function submitForm() {
    const form = document.getElementById('moto-form');
    const formData = new FormData(form);

    fetch('/add_motorcycle', {
        method: 'POST',
        body: formData,
        headers: {
            'X-CSRFToken': document.querySelector('input[name="csrf_token"]').value
        }
    })
    .then(response => {
        if (!response.ok) {
            throw new Error('Ошибка сети');
        }
        return response.json();
    })
    .then(data => {
        if (data.success) {
            if (data.redirect) {
                window.location.href = data.redirect;
            } else {
                window.location.href = '/index';
            }
        } else {
            alert(data.message || 'Произошла ошибка при добавлении');
        }
    })
    .catch(error => {
        console.error('Ошибка:', error);
        alert(error.message || 'Произошла ошибка при добавлении мотоцикла');
    });
}

